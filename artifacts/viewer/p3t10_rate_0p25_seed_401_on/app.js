(() => {
  "use strict";

  const replay = window.WORM_WORLD_REPLAY;
  if (!replay || !Array.isArray(replay.frames) || replay.frames.length === 0) {
    document.body.textContent = "Replay data is missing or empty.";
    return;
  }

  const canvas = document.querySelector("#world");
  const context = canvas.getContext("2d");
  const timeline = document.querySelector("#timeline");
  const play = document.querySelector("#play");
  const speed = document.querySelector("#speed");
  const tombstones = document.querySelector("#tombstones");
  const inspector = document.querySelector("#inspector");
  const step = document.querySelector("#step");
  const time = document.querySelector("#time");
  const population = document.querySelector("#population");
  const configId = document.querySelector("#config-id");

  let frameIndex = 0;
  let selectedId = null;
  let playing = false;
  let previousTimestamp = 0;
  let frameAccumulator = 0;
  let geometry = null;

  timeline.max = String(replay.frames.length - 1);
  configId.textContent = `CONFIG ${replay.config_id.slice(0, 12)} · HASH ${replay.event_hash.slice(0, 12)}`;

  const colorFor = (organism) => {
    if (!organism.active) return "#59635d";
    const hue = parseInt(organism.genome_id.slice(0, 6), 16) % 360;
    return `hsl(${hue} 58% 72%)`;
  };

  const project = (point) => ({
    x: geometry.left + point.x * geometry.scale,
    y: geometry.top + (geometry.heightMeters - point.y) * geometry.scale,
  });

  function resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const bounds = canvas.getBoundingClientRect();
    canvas.width = Math.round(bounds.width * ratio);
    canvas.height = Math.round(bounds.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    draw();
  }

  function drawGrid(frame, width, height) {
    context.fillStyle = "#101914";
    context.fillRect(0, 0, width, height);
    context.strokeStyle = "#26332b";
    context.lineWidth = 1;
    for (let x = 0; x <= frame.width_meters; x += 1) {
      const point = project({ x, y: 0 });
      context.beginPath(); context.moveTo(point.x, geometry.top); context.lineTo(point.x, geometry.bottom); context.stroke();
    }
    for (let y = 0; y <= frame.height_meters; y += 1) {
      const point = project({ x: 0, y });
      context.beginPath(); context.moveTo(geometry.left, point.y); context.lineTo(geometry.right, point.y); context.stroke();
    }
    context.strokeStyle = "#526259";
    context.strokeRect(geometry.left, geometry.top, geometry.worldWidth, geometry.worldHeight);
  }

  function drawResource(resource) {
    const center = project(resource.position);
    const radius = Math.max(5, resource.interaction_radius * geometry.scale);
    const color = resource.kind === "water" ? "99, 204, 218" : "185, 231, 105";
    const gradient = context.createRadialGradient(center.x, center.y, 1, center.x, center.y, radius * 1.5);
    gradient.addColorStop(0, `rgba(${color}, .6)`);
    gradient.addColorStop(1, `rgba(${color}, 0)`);
    context.fillStyle = gradient;
    context.beginPath(); context.arc(center.x, center.y, radius * 1.5, 0, Math.PI * 2); context.fill();
    context.fillStyle = `rgb(${color})`;
    context.beginPath(); context.arc(center.x, center.y, 3.5, 0, Math.PI * 2); context.fill();
  }

  function drawOrganism(organism) {
    if (!organism.active && !tombstones.checked) return;
    const points = organism.segments.map(project);
    if (points.length === 0) return;
    context.save();
    context.globalAlpha = organism.active ? 1 : 0.35;
    context.strokeStyle = colorFor(organism);
    context.lineWidth = selectedId === organism.entity_id ? 8 : 5;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(points[0].x, points[0].y);
    points.slice(1).forEach((point) => context.lineTo(point.x, point.y));
    context.stroke();
    context.fillStyle = selectedId === organism.entity_id ? "#ffffff" : colorFor(organism);
    context.beginPath(); context.arc(points[0].x, points[0].y, 4, 0, Math.PI * 2); context.fill();
    context.restore();
  }

  function updateInspector(frame) {
    const organism = frame.organisms.find((candidate) => candidate.entity_id === selectedId);
    if (!organism) {
      inspector.className = "inspector empty";
      inspector.innerHTML = '<p class="eyebrow">INSPECTOR</p><h2>Select a worm</h2><p>Click a body in the replay to inspect its recorded identity and physiology.</p>';
      return;
    }
    inspector.className = "inspector";
    inspector.innerHTML = `<p class="eyebrow">ORGANISM ${organism.entity_id}</p><h2>${organism.active ? "Active" : "Tombstone"}</h2><dl>
      <dt>Energy</dt><dd>${organism.energy.toFixed(3)}</dd><dt>Hydration</dt><dd>${organism.hydration.toFixed(3)}</dd><dt>Injury</dt><dd>${organism.injury.toFixed(3)}</dd>
      <dt>Genome</dt><dd title="${organism.genome_id}">${organism.genome_id.slice(0, 9)}…</dd><dt>Lineage</dt><dd title="${organism.lineage_id}">${organism.lineage_id.slice(0, 9)}…</dd>
    </dl>`;
  }

  function draw() {
    const frame = replay.frames[frameIndex];
    const bounds = canvas.getBoundingClientRect();
    const margin = 30;
    const scale = Math.min((bounds.width - margin * 2) / frame.width_meters, (bounds.height - margin * 2) / frame.height_meters);
    const worldWidth = frame.width_meters * scale;
    const worldHeight = frame.height_meters * scale;
    geometry = {
      scale, worldWidth, worldHeight, widthMeters: frame.width_meters, heightMeters: frame.height_meters,
      left: (bounds.width - worldWidth) / 2, top: (bounds.height - worldHeight) / 2,
    };
    geometry.right = geometry.left + worldWidth;
    geometry.bottom = geometry.top + worldHeight;
    drawGrid(frame, bounds.width, bounds.height);
    frame.resources.forEach(drawResource);
    frame.organisms.forEach(drawOrganism);
    step.textContent = `STEP ${frame.step_index}`;
    time.textContent = `${frame.elapsed_seconds.toFixed(2)} s`;
    population.textContent = `${frame.organisms.filter((organism) => organism.active).length} ACTIVE`;
    timeline.value = String(frameIndex);
    updateInspector(frame);
  }

  function animation(timestamp) {
    if (!playing) return;
    const delta = previousTimestamp ? timestamp - previousTimestamp : 0;
    previousTimestamp = timestamp;
    frameAccumulator += delta * Number(speed.value) / 120;
    if (frameAccumulator >= 1) {
      const advance = Math.floor(frameAccumulator);
      frameAccumulator -= advance;
      frameIndex = Math.min(frameIndex + advance, replay.frames.length - 1);
      draw();
      if (frameIndex === replay.frames.length - 1) setPlaying(false);
    }
    if (playing) requestAnimationFrame(animation);
  }

  function setPlaying(value) {
    playing = value;
    play.textContent = playing ? "❚❚" : "▶";
    play.setAttribute("aria-label", playing ? "Pause replay" : "Play replay");
    previousTimestamp = 0;
    if (playing) {
      if (frameIndex === replay.frames.length - 1) frameIndex = 0;
      requestAnimationFrame(animation);
    }
  }

  canvas.addEventListener("click", (event) => {
    if (!geometry) return;
    const bounds = canvas.getBoundingClientRect();
    const click = { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
    const candidates = replay.frames[frameIndex].organisms.filter((organism) => organism.active || tombstones.checked);
    let nearest = null;
    let distance = 14;
    candidates.forEach((organism) => organism.segments.forEach((point) => {
      const screen = project(point);
      const candidateDistance = Math.hypot(screen.x - click.x, screen.y - click.y);
      if (candidateDistance < distance) { distance = candidateDistance; nearest = organism; }
    }));
    selectedId = nearest ? nearest.entity_id : null;
    draw();
  });
  play.addEventListener("click", () => setPlaying(!playing));
  timeline.addEventListener("input", () => { frameIndex = Number(timeline.value); setPlaying(false); draw(); });
  tombstones.addEventListener("change", draw);
  window.addEventListener("resize", resize);
  resize();
})();
