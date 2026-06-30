// `plantuml-encoder` ships no types. It deflates + base64-variant-encodes diagram source
// into the path segment a PlantUML/Kroki server expects: `${server}/svg/${encode(src)}`.
declare module 'plantuml-encoder' {
  export function encode(text: string): string
  export function decode(encoded: string): string
  const _default: { encode: typeof encode; decode: typeof decode }
  export default _default
}
