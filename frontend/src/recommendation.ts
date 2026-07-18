import type { VectorizationMode, VectorizationOptions } from './api'

export interface ImageMetrics {
  colorDiversity: number
  colorFamilyCount: number
  coloredPixelRatio: number
  saturatedPixelRatio: number
  inkCoverage: number
  averageBrightness: number
}

export interface VectorizationRecommendation {
  mode: VectorizationMode
  options: VectorizationOptions
  confidence: 'high' | 'medium'
  message: string
}

/**
 * Choose a predictable starting profile from image statistics. This deliberately
 * stays local: the recommendation needs no upload, API key, model download, or
 * LLM and is immediately overridable in the inspector.
 */
export function recommendFromMetrics(metrics: ImageMetrics): VectorizationRecommendation {
  const mostlyWhiteBackground = metrics.averageBrightness > 185
  // A mostly white image can still be a multi-colour logo. Count meaningful
  // hue families separately so a red-and-blue logo is not mistaken for a blue
  // signature merely because its background dominates the pixels.
  const hasMultipleColorFamilies = metrics.colorFamilyCount >= 2
  const mostlySingleInk = !hasMultipleColorFamilies && metrics.inkCoverage < 0.3
  const useLineArt = mostlyWhiteBackground && mostlySingleInk

  if (useLineArt) {
    return {
      mode: 'line-art',
      options: { mode: 'line-art', colorCount: 2, smoothing: 35, minimumComponentArea: 90, useSegmentation: false },
      confidence: mostlyWhiteBackground && metrics.colorFamilyCount <= 1 ? 'high' : 'medium',
      message: 'Line art selected: this looks like a signature, sketch, or single-ink logo. Small specks will be filtered more aggressively.',
    }
  }

  if (metrics.colorDiversity >= 20 && metrics.inkCoverage > 0.5) {
    return {
      mode: 'illustration',
      options: { mode: 'illustration', colorCount: 12, smoothing: 55, minimumComponentArea: 90, useSegmentation: false },
      confidence: 'medium',
      message: 'This looks photo-like or highly detailed. Illustration is the closest fallback, but VectorForge is optimized for flat artwork, not portraits or photographs.',
    }
  }

  const colors = Math.max(3, Math.min(12, Math.round(metrics.colorDiversity)))
  return {
    mode: 'illustration',
    options: { mode: 'illustration', colorCount: colors, smoothing: 50, minimumComponentArea: 55, useSegmentation: false },
    confidence: metrics.saturatedPixelRatio > 0.1 ? 'high' : 'medium',
    message: `Illustration selected: this looks like flat artwork with multiple colors. Starting with ${colors} color layers.`,
  }
}

export async function analyzeImageFile(file: File): Promise<VectorizationRecommendation> {
  const url = URL.createObjectURL(file)
  try {
    const image = await loadImage(url)
    const scale = Math.min(1, 256 / Math.max(image.naturalWidth, image.naturalHeight))
    const width = Math.max(1, Math.round(image.naturalWidth * scale))
    const height = Math.max(1, Math.round(image.naturalHeight * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d', { willReadFrequently: true })
    if (!context) throw new Error('Canvas image analysis is unavailable.')
    context.drawImage(image, 0, 0, width, height)
    return recommendFromMetrics(measurePixels(context.getImageData(0, 0, width, height).data))
  } finally {
    URL.revokeObjectURL(url)
  }
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('The selected image could not be analyzed.'))
    image.src = url
  })
}

function measurePixels(data: Uint8ClampedArray): ImageMetrics {
  const colors = new Set<string>()
  const colorFamilySamples = new Map<number, number>()
  let saturated = 0
  let colored = 0
  let ink = 0
  let brightnessTotal = 0
  const step = Math.max(4, Math.floor(data.length / 4 / 10_000) * 4)
  let samples = 0
  for (let index = 0; index < data.length; index += step) {
    const red = data[index]
    const green = data[index + 1]
    const blue = data[index + 2]
    const maximum = Math.max(red, green, blue)
    const minimum = Math.min(red, green, blue)
    const chroma = maximum - minimum
    const brightness = (red * 0.2126) + (green * 0.7152) + (blue * 0.0722)
    brightnessTotal += brightness
    if (chroma > 40 && maximum > 80) saturated += 1
    if (chroma > 35) {
      colored += 1
      const family = hueFamily(red, green, blue, maximum, minimum)
      colorFamilySamples.set(family, (colorFamilySamples.get(family) ?? 0) + 1)
    }
    if (brightness < 205 || chroma > 35) ink += 1
    colors.add(`${Math.floor(red / 48)}-${Math.floor(green / 48)}-${Math.floor(blue / 48)}`)
    samples += 1
  }
  return {
    colorDiversity: colors.size,
    // Ignore anti-aliasing and JPEG noise. A hue needs to cover at least 0.2%
    // of samples to count as an artwork colour family.
    colorFamilyCount: [...colorFamilySamples.values()].filter((count) => count / samples >= 0.002).length,
    coloredPixelRatio: colored / samples,
    saturatedPixelRatio: saturated / samples,
    inkCoverage: ink / samples,
    averageBrightness: brightnessTotal / samples,
  }
}

function hueFamily(red: number, green: number, blue: number, maximum: number, minimum: number): number {
  const delta = maximum - minimum
  let hue: number
  if (maximum === red) hue = ((green - blue) / delta) % 6
  else if (maximum === green) hue = ((blue - red) / delta) + 2
  else hue = ((red - green) / delta) + 4
  return Math.floor((((hue * 60) + 360) % 360) / 45)
}
