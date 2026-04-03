/**
 * Fondo de partículas (OGL) solo para la página de inicio.
 * OGL se carga vía CDN (ESM); no requiere npm en el proyecto.
 */
import { Renderer, Camera, Transform, Geometry, Program, Mesh } from "https://esm.sh/ogl@1.0.8";

const canvas = document.getElementById("inicio-ogl-particles");
if (!canvas) {
  // No es la plantilla de inicio
} else {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* WebGL1: los shaders usan attribute/varying/gl_FragColor (GLSL 100).
     OGL por defecto pide WebGL2, donde eso falla al enlazar y no se ve nada. */
  const renderer = new Renderer({
    canvas,
    webgl: 1,
    alpha: true,
    depth: false,
    premultipliedAlpha: false,
    antialias: true,
    dpr: Math.min(window.devicePixelRatio || 1, 2),
  });

  const { gl } = renderer;
  if (!gl) {
    canvas.classList.add("inicio-ogl-canvas--hidden");
  } else {

  let camera;
  let mesh;
  let program;
  let scene;

  const count = reduceMotion ? 120 : Math.min(900, Math.floor((window.innerWidth * window.innerHeight) / 3500));

  const positions = new Float32Array(count * 3);
  const randoms = new Float32Array(count);
  const speeds = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 2;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 2;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 0.4;
    randoms[i] = Math.random();
    speeds[i] = 0.6 + Math.random() * 1.4;
  }

  const geometry = new Geometry(gl, {
    position: { size: 3, data: positions },
    aRandom: { size: 1, data: randoms },
    aSpeed: { size: 1, data: speeds },
  });

  const vertex = `
    precision highp float;
    attribute vec3 position;
    attribute float aRandom;
    attribute float aSpeed;
    uniform float uTime;
    uniform vec2 uScale;
    uniform mat4 modelViewMatrix;
    uniform mat4 projectionMatrix;
    varying float vAlpha;

    void main() {
      vec2 p = position.xy * uScale;
      float t = uTime * 0.00035 * aSpeed;
      p.x += sin(t + aRandom * 6.2831853) * 0.04 * uScale.x;
      p.y += cos(t * 0.85 + aRandom * 3.1415926) * 0.035 * uScale.y;
      vec3 pos = vec3(p, position.z);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
      float px = (14.0 + aRandom * 22.0) * (uScale.x > 600.0 ? 1.2 : 1.0);
      gl_PointSize = min(px, 120.0);
      vAlpha = 0.35 + aRandom * 0.5;
    }
  `;

  const fragment = `
    precision highp float;
    varying float vAlpha;
    void main() {
      vec2 c = gl_PointCoord - 0.5;
      float d = length(c);
      if (d > 0.5) discard;
      float soft = smoothstep(0.5, 0.06, d);
      vec3 col = vec3(1.0, 1.0, 1.0);
      gl_FragColor = vec4(col, soft * vAlpha);
    }
  `;

  function makeCamera(w, h) {
    const halfW = w / 2;
    const halfH = h / 2;
    return new Camera(gl, {
      left: -halfW,
      right: halfW,
      top: halfH,
      bottom: -halfH,
      near: 0.1,
      far: 50,
    });
  }

  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h);
    camera = makeCamera(w, h);
    camera.position.z = 8;
    if (program) {
      program.uniforms.uScale.value = [w * 0.55, h * 0.55];
    }
  }

  program = new Program(gl, {
    vertex,
    fragment,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    cullFace: false,
    uniforms: {
      uTime: { value: 0 },
      uScale: { value: [1, 1] },
    },
  });

  scene = new Transform();
  mesh = new Mesh(gl, { geometry, program, mode: gl.POINTS, frustumCulled: false });
  mesh.setParent(scene);

  resize();
  window.addEventListener("resize", resize);

  let start = performance.now();
  let raf = 0;

  function frame(now) {
    program.uniforms.uTime.value = now - start;
    renderer.render({ scene, camera });
    if (!reduceMotion) {
      raf = requestAnimationFrame(frame);
    }
  }

  if (reduceMotion) {
    program.uniforms.uTime.value = 0;
    renderer.render({ scene, camera });
  } else {
    raf = requestAnimationFrame(frame);
  }

  document.addEventListener("visibilitychange", () => {
    if (reduceMotion) return;
    if (document.hidden) {
      cancelAnimationFrame(raf);
      raf = 0;
    } else if (!raf) {
      start = performance.now() - program.uniforms.uTime.value;
      raf = requestAnimationFrame(frame);
    }
  });
  }
}
