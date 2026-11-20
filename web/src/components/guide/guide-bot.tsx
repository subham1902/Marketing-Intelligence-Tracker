"use client";

import { useEffect, useRef } from "react";

/**
 * "Volt", the guide's 3D companion (three.js, loaded lazily).
 * A rounded teal head with eyes that follow the pointer, blinks, bobs gently,
 * and spins its antenna ring while the guide is thinking. Static when the user
 * prefers reduced motion. Falls back to nothing if WebGL is unavailable.
 */
export function GuideBot({
  size = 64,
  thinking = false,
  className,
}: {
  size?: number;
  thinking?: boolean;
  className?: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const thinkingRef = useRef(thinking);
  thinkingRef.current = thinking;

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    const el = host.current;
    if (!el) return;

    (async () => {
      const THREE = await import("three");
      if (disposed) return;
      let renderer: import("three").WebGLRenderer;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      } catch {
        return; // no WebGL: the launcher still works without the bot
      }
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      renderer.setPixelRatio(dpr);
      renderer.setSize(size, size);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      el.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
      camera.position.set(0, 0.15, 6.2);

      scene.add(new THREE.HemisphereLight(0xdff9ff, 0x0b1622, 1.6));
      const key = new THREE.DirectionalLight(0xffffff, 2.2);
      key.position.set(2.5, 3, 4);
      scene.add(key);
      const rim = new THREE.PointLight(0x2ee6c2, 14, 10);
      rim.position.set(-2.5, 1.5, -1.5);
      scene.add(rim);

      const bot = new THREE.Group();
      scene.add(bot);

      // Head: a rounded box (capsule-ish), charge-teal with a soft sheen.
      const headGeo = new THREE.SphereGeometry(1.25, 48, 48);
      headGeo.scale(1.12, 0.95, 1);
      const headMat = new THREE.MeshPhysicalMaterial({
        color: 0x14b8a6, roughness: 0.32, metalness: 0.15, clearcoat: 0.8, clearcoatRoughness: 0.25,
      });
      const head = new THREE.Mesh(headGeo, headMat);
      bot.add(head);

      // Visor: dark glass face plate.
      const visorGeo = new THREE.SphereGeometry(1.0, 48, 32, -Math.PI * 0.42, Math.PI * 0.84, Math.PI * 0.3, Math.PI * 0.38);
      const visor = new THREE.Mesh(
        visorGeo,
        new THREE.MeshPhysicalMaterial({ color: 0x0b1622, roughness: 0.12, metalness: 0.4, clearcoat: 1 }),
      );
      visor.scale.set(1.18, 1.05, 1.16);
      visor.position.z = 0.12;
      bot.add(visor);

      // Eyes: glowing saffron-white capsules on the visor.
      const eyeMat = new THREE.MeshBasicMaterial({ color: 0xfff1d6 });
      const eyeGeo = new THREE.CapsuleGeometry(0.11, 0.16, 6, 12);
      const eyes = new THREE.Group();
      const eyeL = new THREE.Mesh(eyeGeo, eyeMat);
      const eyeR = new THREE.Mesh(eyeGeo, eyeMat);
      eyeL.position.set(-0.36, 0.05, 1.12);
      eyeR.position.set(0.36, 0.05, 1.12);
      eyes.add(eyeL, eyeR);
      bot.add(eyes);

      // Antenna with a ring that spins while thinking.
      const stem = new THREE.Mesh(
        new THREE.CylinderGeometry(0.05, 0.05, 0.5, 12),
        new THREE.MeshStandardMaterial({ color: 0x0e8c8a }),
      );
      stem.position.y = 1.35;
      bot.add(stem);
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.14, 20, 20), new THREE.MeshBasicMaterial({ color: 0xe8912d }));
      tip.position.y = 1.66;
      bot.add(tip);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.3, 0.035, 10, 40),
        new THREE.MeshBasicMaterial({ color: 0x2ee6c2, transparent: true, opacity: 0.85 }),
      );
      ring.position.y = 1.66;
      ring.rotation.x = Math.PI / 2.4;
      bot.add(ring);

      // Little ear pods.
      const podMat = new THREE.MeshStandardMaterial({ color: 0x0e8c8a, roughness: 0.4 });
      [-1, 1].forEach((s) => {
        const pod = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.18, 24), podMat);
        pod.rotation.z = Math.PI / 2;
        pod.position.set(s * 1.42, 0, 0);
        bot.add(pod);
      });

      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const target = { x: 0, y: 0 };
      const onMove = (e: PointerEvent) => {
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        target.x = Math.max(-1, Math.min(1, (e.clientX - cx) / (window.innerWidth / 2)));
        target.y = Math.max(-1, Math.min(1, (e.clientY - cy) / (window.innerHeight / 2)));
      };
      window.addEventListener("pointermove", onMove);

      let raf = 0;
      const clock = new THREE.Clock();
      let nextBlink = 2 + Math.random() * 3;
      const look = { x: 0, y: 0 };

      const frame = () => {
        const t = clock.getElapsedTime();
        look.x += (target.x - look.x) * 0.08;
        look.y += (target.y - look.y) * 0.08;
        bot.rotation.y = look.x * 0.55;
        bot.rotation.x = look.y * 0.35;
        eyes.position.x = look.x * 0.08;
        eyes.position.y = -look.y * 0.06;
        if (!reduce) {
          bot.position.y = Math.sin(t * 1.6) * 0.07;
          ring.rotation.z += thinkingRef.current ? 0.18 : 0.012;
          (ring.material as import("three").MeshBasicMaterial).opacity = thinkingRef.current
            ? 0.6 + Math.sin(t * 10) * 0.35
            : 0.85;
          // Blink.
          const since = t - nextBlink;
          const k = since > 0 && since < 0.16 ? 1 - Math.sin((since / 0.16) * Math.PI) : 1;
          eyeL.scale.y = eyeR.scale.y = Math.max(0.1, k);
          if (since >= 0.16) nextBlink = t + 2.5 + Math.random() * 3.5;
          // Eyes squint while thinking.
          if (thinkingRef.current) eyeL.scale.y = eyeR.scale.y = 0.55;
        }
        renderer.render(scene, camera);
        raf = requestAnimationFrame(frame);
      };
      frame();

      cleanup = () => {
        cancelAnimationFrame(raf);
        window.removeEventListener("pointermove", onMove);
        renderer.dispose();
        scene.traverse((o) => {
          const m = o as import("three").Mesh;
          m.geometry?.dispose?.();
          const mat = m.material as import("three").Material | undefined;
          mat?.dispose?.();
        });
        renderer.domElement.remove();
      };
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [size]);

  return <div ref={host} className={className} style={{ width: size, height: size }} aria-hidden />;
}
