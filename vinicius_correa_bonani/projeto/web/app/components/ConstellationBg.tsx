"use client";

import { useEffect, useRef } from "react";

// brilho: alfa máximo das linhas (0 a 1). A landing usa 0.55 para a
// constelação atravessar os painéis de vidro; o dashboard fica no padrão.
export default function ConstellationBg({ brilho = 0.35 }: { brilho?: number }) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const el = canvasRef.current;
        if (!el) return;
        const context = el.getContext("2d");
        if (!context) return;
        const canvas = el;        // trava o tipo não-nulo p/ os closures (resize/draw)
        const ctx = context;


        const GREEN = "118,185,0";
        const DPR = Math.min(window.devicePixelRatio || 1, 2);
        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        let W = 0, H = 0, LINK = 0, raf = 0;
        let particles: { x: number; y: number; vx: number; vy: number }[] = [];
        const mouse = { x: null as number | null, y: null as number | null };

        function resize() {
            W = canvas.width = Math.floor(window.innerWidth * DPR);
            H = canvas.height = Math.floor(window.innerHeight * DPR);
            canvas.style.width = window.innerWidth + "px";
            canvas.style.height = window.innerHeight + "px";
            LINK = 140 * DPR;
            const count = Math.min(150, Math.floor((window.innerWidth * window.innerHeight) / 11000));
            particles = Array.from({ length: count }, () => ({
                x: Math.random() * W,
                y: Math.random() * H,
                vx: (Math.random() - 0.5) * 0.35 * DPR,
                vy: (Math.random() - 0.5) * 0.35 * DPR,
            }));
        }

        function draw() {
            ctx.clearRect(0, 0, W, H);
            for (const p of particles) {
                if (!reduced) {
                    p.x += p.vx; p.y += p.vy;
                    if (p.x < 0 || p.x > W) p.vx *= -1;
                    if (p.y < 0 || p.y > H) p.vy *= -1;
                }
            }
            for (let i = 0; i < particles.length; i++) {
                const a = particles[i];
                for (let j = i + 1; j < particles.length; j++) {
                    const b = particles[j];
                    const d = Math.hypot(a.x - b.x, a.y - b.y);
                    if (d < LINK) {
                        ctx.strokeStyle = "rgba(" + GREEN + "," + (1 - d / LINK) * brilho + ")";
                        ctx.lineWidth = DPR;
                        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
                    }
                }
                if (mouse.x !== null && mouse.y !== null) {
                    const d = Math.hypot(a.x - mouse.x, a.y - mouse.y);
                    const R = LINK * 1.4;
                    if (d < R) {
                        ctx.strokeStyle = "rgba(" + GREEN + "," + (1 - d / R) * brilho + ")";
                        ctx.lineWidth = DPR;
                        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
                    }
                }
                ctx.fillStyle = "rgba(" + GREEN + ",0.85)";
                ctx.beginPath(); ctx.arc(a.x, a.y, 1.5 * DPR, 0, Math.PI * 2); ctx.fill();
            }
            if (!reduced) raf = requestAnimationFrame(draw);
        }

        const onMove = (e: MouseEvent) => { mouse.x = e.clientX * DPR; mouse.y = e.clientY * DPR; };
        const onOut = () => { mouse.x = mouse.y = null; };

        resize();
        draw();
        window.addEventListener("resize", resize);
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseout", onOut);

        return () => {
            cancelAnimationFrame(raf);
            window.removeEventListener("resize", resize);
            window.removeEventListener("mousemove", onMove);
            window.removeEventListener("mouseout", onOut);
        };
    }, [brilho]);

    return <canvas ref={canvasRef} className="fixed inset-0 -z-10" aria-hidden="true" />;
}
