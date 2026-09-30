// Resolves the bare "three" specifier to the vendored build (the browser uses the importmap in web/life.html).
const THREE = new URL("../../web/vendor/three/build/three.module.min.js", import.meta.url).href;
const ADDONS = new URL("../../web/vendor/three/examples/jsm/", import.meta.url).href;
export async function resolve(spec, ctx, next) {
  if (spec === "three") return { url: THREE, shortCircuit: true };
  if (spec.startsWith("three/addons/")) return { url: ADDONS + spec.slice("three/addons/".length), shortCircuit: true };
  return next(spec, ctx);
}
