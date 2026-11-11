import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';

const canvas = document.getElementById('scene');
const TOWER_URL = '/models/lingxiao_tower.glb';
const SITE_URL = '/models/site.glb';
const TOWER_H = 40.98;

/* ------------------------------ 渲染器 ------------------------------ */
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  powerPreference: 'high-performance',
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.56;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

/* ------------------------------ 场景 ------------------------------ */
const scene = new THREE.Scene();

function makeBackground() {
  const c = document.createElement('canvas');
  c.width = c.height = 1024;
  const ctx = c.getContext('2d');
  // 穹顶：天顶墨蓝 → 地平线暖赭
  const g = ctx.createLinearGradient(0, 0, 0, 1024);
  g.addColorStop(0.00, '#0A0A10');
  g.addColorStop(0.34, '#1A1219');
  g.addColorStop(0.58, '#3B2318');
  g.addColorStop(0.72, '#5A3220');
  g.addColorStop(0.84, '#2A1810');
  g.addColorStop(1.00, '#0B0705');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 1024, 1024);
  // 地平线一抹余晖
  const g2 = ctx.createRadialGradient(700, 700, 20, 700, 700, 520);
  g2.addColorStop(0.00, 'rgba(255,168,96,0.34)');
  g2.addColorStop(0.42, 'rgba(214,118,58,0.11)');
  g2.addColorStop(1.00, 'rgba(0,0,0,0)');
  ctx.fillStyle = g2;
  ctx.fillRect(0, 0, 1024, 1024);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
scene.background = makeBackground();
scene.fog = new THREE.FogExp2(0x1C1208, 0.0052);

const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.4, 4000);

const controls = new OrbitControls(camera, canvas);
controls.target.set(0, TOWER_H * 0.44, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.055;
controls.enablePan = false;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.42;
controls.minDistance = 26;
controls.maxDistance = 260;
controls.minPolarAngle = Math.PI * 0.16;
controls.maxPolarAngle = Math.PI * 0.545;
controls.update();

let autoResumeTimer = null;
canvas.addEventListener('pointerdown', () => {
  controls.autoRotate = false;
  if (autoResumeTimer) clearTimeout(autoResumeTimer);
});
canvas.addEventListener('pointerup', () => {
  if (autoResumeTimer) clearTimeout(autoResumeTimer);
  autoResumeTimer = setTimeout(() => { controls.autoRotate = true; }, 4500);
});
canvas.addEventListener('wheel', () => {
  controls.autoRotate = false;
  if (autoResumeTimer) clearTimeout(autoResumeTimer);
  autoResumeTimer = setTimeout(() => { controls.autoRotate = true; }, 4500);
}, { passive: true });

/* ------------------------------ 光照 ------------------------------ */
scene.add(new THREE.HemisphereLight(0xA8BCDE, 0x3A2A1E, 1.06));

const key = new THREE.DirectionalLight(0xffe6c8, 3.50);
key.position.set(54, 126, -46);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.near = 40;
key.shadow.camera.far = 380;
key.shadow.camera.left = -62;
key.shadow.camera.right = 62;
key.shadow.camera.top = 74;
key.shadow.camera.bottom = -30;
key.shadow.bias = -0.0008;
key.shadow.normalBias = 0.07;
scene.add(key);

const fill = new THREE.DirectionalLight(0x8CA4FF, 1.18);
fill.position.set(-78, 34, 52);
scene.add(fill);

const rim = new THREE.DirectionalLight(0xffa24e, 1.72);
rim.position.set(-18, 48, 94);
scene.add(rim);

const front = new THREE.DirectionalLight(0xffd9b8, 0.98);
front.position.set(34, 22, -72);
scene.add(front);

const sideWarm = new THREE.DirectionalLight(0xffb072, 0.52);
sideWarm.position.set(-62, 34, -40);
scene.add(sideWarm);

const floorGlow = new THREE.PointLight(0xff9a52, 132, 74, 2);
floorGlow.position.set(0, 3.4, -8);
scene.add(floorGlow);

// 院内几处灯火：山门、重门、塔前、后殿
[[0, 5.2, -60], [0, 4.8, -37], [5.0, 3.4, -20], [-5.0, 3.4, -20], [0, 5.4, 30]].forEach(([x, y, z]) => {
  const p = new THREE.PointLight(0xffa656, 40, 34, 2);
  p.position.set(x, y, z);
  scene.add(p);
});

// 院心柔光：模拟院内漫反射，避免庭院在夜景里塌成黑洞
[[0, 13, -34, 205], [0, 11, 22, 170], [-16, 9, 6, 130], [16, 9, 6, 130]].forEach(([x, y, z, i]) => {
  const p = new THREE.PointLight(0xffb478, i, 56, 2);
  p.position.set(x, y, z);
  scene.add(p);
});

// 塔身亮化：台基四角地埋投光灯上射，做出塔身自下而上的暖光渐变
[[8.4, 8.4], [-8.4, 8.4], [10.6, -10.6], [-10.6, -10.6]].forEach(([x, z]) => {
  // v3 细节密度翻倍后回调上射灯：强度 300→250、照射点 30→25 m，
  // 配合瓦面单独压暗，保留暖光渐变但不把翼角烧白
  const s = new THREE.SpotLight(0xffcf9e, 250, 92, 0.48, 0.95, 1.05);
  s.position.set(x, 1.6, z);
  s.target.position.set(0, 25, 0);
  scene.add(s);
  scene.add(s.target);
});

/* ------------------------------ 灯笼 ------------------------------ */
// 檐下悬挂的红灯笼：既是光源也是夜里的视觉落点
const lanternBody = new THREE.SphereGeometry(0.17, 10, 8);
const lanternCap = new THREE.CylinderGeometry(0.055, 0.055, 0.05, 6);
const lanternCord = new THREE.CylinderGeometry(0.012, 0.012, 0.42, 4);
const matLit = new THREE.MeshBasicMaterial({ color: 0xffb267 });
const matCap = new THREE.MeshBasicMaterial({ color: 0x8a3512 });

const LANTERNS = [
  [-4.4, 4.9, -63.4], [4.4, 4.9, -63.4],
  [-3.7, 4.5, -40.2], [3.7, 4.5, -40.2],
  [-6.7, 5.4, 24.3], [6.7, 5.4, 24.3],
  [-6.2, 3.5, -14.4], [6.2, 3.5, -14.4],
];
for (const [x, y, z] of LANTERNS) {
  const b = new THREE.Mesh(lanternBody, matLit);
  b.position.set(x, y, z);
  b.scale.set(1, 1.28, 1);
  scene.add(b);
  for (const dy of [0.24, -0.24]) {
    const cap = new THREE.Mesh(lanternCap, matCap);
    cap.position.set(x, y + dy, z);
    scene.add(cap);
  }
  const cord = new THREE.Mesh(lanternCord, matCap);
  cord.position.set(x, y + 0.48, z);
  scene.add(cord);
  const pl = new THREE.PointLight(0xff9a4a, 30, 20, 2);
  pl.position.set(x, y, z);
  scene.add(pl);
}

/* ------------------------------ 环境反射 ------------------------------ */
const pmrem = new THREE.PMREMGenerator(renderer);
const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
scene.environment = envRT.texture;
scene.environmentIntensity = 0.22;
pmrem.dispose();

/* ------------------------------ 星空 ------------------------------ */
const starCount = 1500;
const sPos = new Float32Array(starCount * 3);
const sSize = new Float32Array(starCount);
const sPhase = new Float32Array(starCount);
for (let i = 0; i < starCount; i++) {
  const r = 220 + Math.random() * 620;
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  sPos[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
  sPos[i * 3 + 1] = Math.abs(r * Math.cos(phi)) * 0.9 + 40;
  sPos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
  sSize[i] = 0.5 + Math.pow(Math.random(), 3.2) * 2.8;
  sPhase[i] = Math.random() * Math.PI * 2;
}
const starGeo = new THREE.BufferGeometry();
starGeo.setAttribute('position', new THREE.BufferAttribute(sPos, 3));
starGeo.setAttribute('aSize', new THREE.BufferAttribute(sSize, 1));
starGeo.setAttribute('aPhase', new THREE.BufferAttribute(sPhase, 1));

const starMat = new THREE.ShaderMaterial({
  transparent: true,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
  uniforms: { uTime: { value: 0 } },
  vertexShader: /* glsl */`
    attribute float aSize;
    attribute float aPhase;
    uniform float uTime;
    varying float vAlpha;
    void main() {
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = aSize * (320.0 / max(-mv.z, 1.0));
      gl_Position = projectionMatrix * mv;
      vAlpha = 0.24 + 0.58 * (0.5 + 0.5 * sin(uTime * 0.7 + aPhase));
      vAlpha *= smoothstep(30.0, 140.0, position.y);
    }
  `,
  fragmentShader: /* glsl */`
    varying float vAlpha;
    void main() {
      vec2 d = gl_PointCoord - vec2(0.5);
      float r = length(d);
      if (r > 0.5) discard;
      float a = smoothstep(0.5, 0.02, r) * vAlpha;
      gl_FragColor = vec4(vec3(1.0, 0.92, 0.78), a);
    }
  `,
});
const stars = new THREE.Points(starGeo, starMat);
scene.add(stars);

/* ------------------------------ 塔基暖光斑 ------------------------------ */
function makeFloorGlow() {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(256, 256, 0, 256, 256, 256);
  g.addColorStop(0.00, 'rgba(255,170,96,0.44)');
  g.addColorStop(0.32, 'rgba(255,140,62,0.17)');
  g.addColorStop(0.64, 'rgba(196,96,38,0.045)');
  g.addColorStop(1.00, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 512, 512);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshBasicMaterial({
    map: tex, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), mat);
  m.rotation.x = -Math.PI / 2;
  m.position.y = 0.04;
  return m;
}
scene.add(makeFloorGlow());

/* ------------------------------ 加载模型 ------------------------------ */
const loader = new GLTFLoader();
let tower = null;
let site = null;
const shellMats = new Set();
const innerMats = new Set();

const MAX_ANISO = renderer.capabilities.getMaxAnisotropy();

function prepModel(root, isSite) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const isGold = /Finial|Gold/i.test(o.name);
    const isInner = !isSite && /Heart_Column/i.test(o.name);
    const isShell = !isSite && /Body_Upper|Eave_Upper|Dougong_Wood|Body_Wood_Railing/i.test(o.name);
    mats.forEach((m) => {
      if (isInner) innerMats.add(m);
      else if (isShell) shellMats.add(m);
      m.side = THREE.DoubleSide;
      m.envMapIntensity = isGold ? 1.1 : 0.22;
      // 掠射角下的铺地/屋面必须开各向异性，否则 mipmap 会把细节糊成色块
      for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap']) {
        const t = m[k];
        if (!t) continue;
        t.anisotropy = MAX_ANISO;
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.needsUpdate = true;
      }
      m.shadowSide = THREE.DoubleSide;
      if (isGold) {
        m.emissive = new THREE.Color(0x8a6218);
        m.emissiveIntensity = 0.12;
      }
      // 叶片给一点自发光，夜景里不至于糊成黑块
      if (isSite && /S_Leaf/i.test(o.name)) {
        m.emissive = new THREE.Color(0x24300f);
        m.emissiveIntensity = 0.30;
      }
    });
  });
  scene.add(root);
}

let loaded = 0;
const loaderTxt = () => document.querySelector('.loader-txt');

function onOneDone() {
  loaded += 1;
  if (loaded >= 2) {
    renderer.shadowMap.needsUpdate = true;
    setTimeout(() => { renderer.shadowMap.autoUpdate = false; }, 900);
    document.getElementById('loader').classList.add('done');
  }
}

loader.load(SITE_URL, (gltf) => {
  site = gltf.scene;
  prepModel(site, true);
  onOneDone();
}, undefined, (err) => {
  console.error('场地加载失败', err);
  onOneDone();
});

loader.load(TOWER_URL, (gltf) => {
  tower = gltf.scene;
  prepModel(tower, false);
  onOneDone();
}, (e) => {
  if (!e.total) return;
  const pct = Math.round((e.loaded / e.total) * 100);
  const el = loaderTxt();
  if (el) el.firstChild.nodeValue = pct < 100 ? `正在起塔 ${pct}%` : '正在起塔';
}, (err) => {
  console.error('塔模型加载失败', err);
  const el = loaderTxt();
  if (el) el.textContent = '模型加载失败，请检查 /models/';
  onOneDone();
});

/* ------------------------------ 剖视 ------------------------------ */
const innerLight = new THREE.PointLight(0xffc78a, 0, 44, 2);
innerLight.position.set(0, 24, 0);
scene.add(innerLight);

const xrayBtn = document.getElementById('xray');
let xrayOn = false;

function applyXray(on) {
  xrayOn = on;
  xrayBtn.classList.toggle('on', on);
  xrayBtn.setAttribute('aria-pressed', on ? 'true' : 'false');

  shellMats.forEach((m) => {
    m.transparent = on;
    m.opacity = on ? 0.16 : 1.0;
    m.depthWrite = !on;
    m.needsUpdate = true;
  });
  innerMats.forEach((m) => {
    m.emissive = new THREE.Color(on ? 0xff9c46 : 0x000000);
    m.emissiveIntensity = on ? 0.26 : 0.0;
    m.needsUpdate = true;
  });
  innerLight.intensity = on ? 140 : 0;
  if (window.__three && window.__three.bloom) {
    window.__three.bloom.strength = on ? 0.15 : 0.34;
  }

  if (on) {
    controls.target.set(0, 24, 0);
    const dir = camera.position.clone().sub(controls.target).normalize();
    camera.position.copy(controls.target).addScaledVector(dir, 58);
    controls.update();
  }
}

if (xrayBtn) xrayBtn.addEventListener('click', () => applyXray(!xrayOn));
window.addEventListener('keydown', (e) => {
  if (e.key === 'x' || e.key === 'X') applyXray(!xrayOn);
});

/* ------------------------------ 后期 ------------------------------ */
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.22, 0.60, 0.88
);
composer.addPass(bloom);
composer.addPass(new OutputPass());

/* ------------------------------ 视口偏移 ------------------------------ */
function updateCamera() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  const offset = w > 860 ? Math.min(190, w * 0.115) : 0;
  camera.setViewOffset(w, h, offset, 0, w, h);
  camera.updateProjectionMatrix();

  renderer.setSize(w, h, false);
  composer.setSize(w, h);
  renderer.shadowMap.needsUpdate = true;
  setTimeout(() => { if (tower) renderer.shadowMap.autoUpdate = false; }, 260);
}
updateCamera();
window.addEventListener('resize', () => {
  renderer.shadowMap.autoUpdate = true;
  updateCamera();
  setTimeout(() => { if (tower) renderer.shadowMap.autoUpdate = false; }, 420);
});

/* ------------------------------ 面板折叠 ------------------------------ */
const panelEl = document.querySelector('.panel');
const panelToggle = document.getElementById('panelToggle');

function isMobileLayout() {
  return window.innerWidth <= 860;
}
function setCollapsed(on) {
  panelEl.classList.toggle('collapsed', on);
  panelToggle.setAttribute('aria-label', on ? '展开详情' : '收起详情');
}
if (panelToggle) {
  panelToggle.addEventListener('click', () => setCollapsed(!panelEl.classList.contains('collapsed')));
}
setCollapsed(isMobileLayout());
let _wasMobile = isMobileLayout();
window.addEventListener('resize', () => {
  const now = isMobileLayout();
  if (now !== _wasMobile) {
    setCollapsed(now);
    _wasMobile = now;
  }
});

/* ------------------------------ 部位标注 ------------------------------ */
// 坐标已换算到 Three（南 = -Z）
const SPOTS = [
  { g: 'tower', t: "须弥座", d: "八角形砖砌台基，束腰嵌清雍正谕旨石刻", x: 4.3, y: 1.15, z: -4.2 },
  { g: 'tower', t: "首层圆拱门", d: "四正面辟圆拱形塔门，塔心室顶部作穹窿顶", x: 1.6, y: 4.6, z: -4.0 },
  { g: 'tower', t: "平座勾栏", d: "二层以上逐层设平座，由勾栏与斗拱承托", x: 2.9, y: 13.4, z: -2.7 },
  { g: 'tower', t: "转角铺作", d: "四层以上斗拱与各层檐皆改木制，金代更建", x: 2.3, y: 23.2, z: -2.2 },
  { g: 'tower', t: "塔心柱", d: "四层起立木质中心柱，八根扒梁放射连接塔壁", x: 0, y: 27.5, z: 0, needXray: true },
  { g: 'tower', t: "塔刹", d: "覆钵、相轮、宝盖、仰月、宝珠自下而上叠成", x: 0, y: 39.4, z: 0 },

  { g: 'site', t: "四柱三门牌坊", d: "临中山东路，明间悬「天宁寺」匾，背面题「古刹无塵」", x: 0, y: 8.6, z: -84 },
  { g: 'site', t: "山门", d: "三开间歇山，中辟券门，两侧设掖门，前跨石桥", x: 0, y: 9.4, z: -60 },
  { g: 'site', t: "重门", d: "元代遗构，三间皆辟门；门前石狮蹲踞，鬃毛螺旋至颈", x: 0, y: 7.6, z: -37 },
  { g: 'site', t: "前殿遗址", d: "正殿五间、前承抱厦三楹，今存柱础阵列与断续残墙", x: 0, y: 3.2, z: -22.5 },
  { g: 'site', t: "宋槐", d: "寺内旧物，与清榆各一株，为塔院仅存的活体遗存", x: 20.6, y: 9.5, z: 7.4 },
  { g: 'site', t: "后殿", d: "五间歇山，殿后即后院；清同治志称「殿后浮图九级」", x: 0, y: 10.2, z: 30 },
  { g: 'site', t: "幡杆", d: "一进院中轴两侧立杆悬幡，为法会与庙市的标识", x: 7.4, y: 11.4, z: -49.6 },
  { g: 'site', t: "明清碑刻", d: "塔院存古碑八通，分列前殿遗址两侧，碑首、碑座俱全", x: 14.6, y: 2.9, z: -26.2 },
  { g: 'site', t: "石渠与石桥", d: "山门前跨单孔石桥，桥下石渠东西贯流，两岸压面石收边", x: 0, y: 2.4, z: -70 },
];

const spotLayer = document.getElementById('spots');
const spotEls = SPOTS.map((sp) => {
  const el = document.createElement('div');
  el.className = 'spot';
  el.innerHTML = `<span class="dot"></span><span class="tag">${sp.t}</span><span class="note">${sp.d}</span>`;
  el.querySelector('.dot').addEventListener('click', (e) => {
    e.stopPropagation();
    el.classList.toggle('on');
  });
  spotLayer.appendChild(el);
  return el;
});
document.addEventListener('click', () => {
  spotEls.forEach((el) => el.classList.remove('on'));
});

const _v = new THREE.Vector3();
let spotGroup = 'tower';

function updateSpots() {
  const w = window.innerWidth;
  const h = window.innerHeight;

  SPOTS.forEach((sp, i) => {
    const el = spotEls[i];
    if (sp.needXray && !xrayOn) {
      el.style.opacity = '0';
      el.style.visibility = 'hidden';
      return;
    }
    if (sp.g !== spotGroup) {
      el.style.opacity = '0';
      el.style.visibility = 'hidden';
      return;
    }
    el.style.visibility = 'visible';

    _v.set(sp.x, sp.y, sp.z).project(camera);
    const sx = (_v.x * 0.5 + 0.5) * w;
    const sy = (-_v.y * 0.5 + 0.5) * h;
    el.style.transform = `translate(${sx}px, ${sy}px)`;

    // 背后剔除：以相机方位判断
    let vis = 1;
    const dx = camera.position.x - sp.x;
    const dz = camera.position.z - sp.z;
    const d2 = Math.hypot(dx, dz);
    if (d2 > 1.0) {
      const nx = -sp.x / Math.max(Math.hypot(sp.x, sp.z), 1e-3);
      const nz = -sp.z / Math.max(Math.hypot(sp.x, sp.z), 1e-3);
      const facing = (dx * nx + dz * nz) / Math.max(d2, 1e-3);
      vis = facing < -0.12 ? 0 : (facing < 0.22 ? 0.3 : 1);
    }
    if (sx < 70 || sx > w - 70 || sy < 46 || sy > h - 40) vis *= 0.3;
    el.style.opacity = String(vis * (xrayOn ? 0.95 : 0.86));
    el.style.pointerEvents = vis > 0.5 ? 'auto' : 'none';
  });
}

/* ------------------------------ 机位 ------------------------------ */
const VIEWS = {
  full:  { pos: [47, 31, -72],  target: [0, 20.5, -1],  xray: false, group: 'tower' },
  low:   { pos: [33, 10, -48],  target: [0, 23.5, 0],   xray: false, group: 'tower' },
  top:   { pos: [16, 37, -19],  target: [0, 32.5, 0],   xray: false, group: 'tower' },
  inner: { pos: [26, 32, -30],  target: [0, 26, 0],     xray: true,  group: 'tower' },
  site:  { pos: [76, 50, -104], target: [0, 7, -17],    xray: false, group: 'site' },
};

let tween = null;
const viewBtns = Array.from(document.querySelectorAll('.views button'));

function viewScale() {
  return window.innerWidth <= 860 ? 1.32 : 1.0;
}
function viewPos(v) {
  const k = viewScale();
  return new THREE.Vector3(v.pos[0] * k, v.pos[1] * k, v.pos[2] * k);
}

function flyTo(name) {
  const v = VIEWS[name];
  if (!v) return;
  viewBtns.forEach((b) => b.classList.toggle('on', b.dataset.view === name));
  controls.autoRotate = false;
  if (autoResumeTimer) clearTimeout(autoResumeTimer);
  spotGroup = v.group || 'tower';

  tween = {
    t: 0,
    dur: 1.4,
    p0: camera.position.clone(),
    p1: viewPos(v),
    t0: controls.target.clone(),
    t1: new THREE.Vector3(...v.target),
    xray: v.xray,
    name,
  };
  if (v.xray !== xrayOn) applyXray(v.xray);
}

viewBtns.forEach((b) => b.addEventListener('click', () => flyTo(b.dataset.view)));

let _camInit = false;
function initCamOnce() {
  if (_camInit) return;
  _camInit = true;
  const v = VIEWS.full;
  camera.position.copy(viewPos(v));
  controls.target.set(...v.target);
  controls.update();
}
initCamOnce();

function stepTween(dt) {
  if (!tween) return;
  tween.t += dt;
  const k = Math.min(1, tween.t / tween.dur);
  const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
  camera.position.lerpVectors(tween.p0, tween.p1, e);
  controls.target.lerpVectors(tween.t0, tween.t1, e);
  if (k >= 1) {
    if (tween.name !== 'inner') {
      autoResumeTimer = setTimeout(() => { controls.autoRotate = true; }, 3400);
    }
    tween = null;
  }
}

/* ------------------------------ 全屏 ------------------------------ */
const fsBtn = document.getElementById('fs');

function syncFullscreen() {
  const on = !!document.fullscreenElement;
  fsBtn.classList.toggle('on', on);
  fsBtn.setAttribute('aria-label', on ? '退出全屏（F）' : '全屏（F）');
}

fsBtn.addEventListener('click', async () => {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
    } else {
      await document.exitFullscreen();
    }
  } catch (e) {
    console.warn('fullscreen unavailable', e);
  }
});

document.addEventListener('fullscreenchange', syncFullscreen);
window.addEventListener('keydown', (e) => {
  if (e.key === 'f' || e.key === 'F') {
    if (e.target && /input|textarea/i.test(e.target.tagName)) return;
    fsBtn.click();
  }
});
syncFullscreen();

/* ------------------------------ 循环 ------------------------------ */
const clock = new THREE.Clock();

function animate() {
  const dt = clock.getDelta();
  const t = clock.elapsedTime;

  starMat.uniforms.uTime.value = t;
  stars.rotation.y = t * 0.0035;

  stepTween(dt);
  controls.update();
  updateSpots();
  composer.render();
  requestAnimationFrame(animate);
}
window.__three = { camera, controls, scene, renderer, composer, bloom };
animate();
