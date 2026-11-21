'use strict';
const gallery = document.getElementById('gallery');
const search = document.getElementById('search');
const modal = document.getElementById('player-modal');
const fullPlayer = document.getElementById('full-player');
const modalTitle = document.getElementById('modal-title');
const modalCaption = document.getElementById('modal-caption');
let videos = [];
let lastSignature = '';
let selectedFilter = '';

function formatBytes(n) {
  if (!n) return '0 B';
  const unit = Math.min(Math.floor(Math.log(n) / Math.log(1024)), 3);
  return `${(n / (1024 ** unit)).toFixed(unit === 0 ? 0 : 1)} ${['B','KiB','MiB','GiB'][unit]}`;
}
function openPlayer(item) {
  stopPreviews();
  modalTitle.textContent = item.filename;
  modalCaption.textContent = `${item.producer} · ${formatBytes(item.final_bytes)}${item.compressed ? ' · compressed' : ''}`;
  fullPlayer.src = item.stream_url;
  modal.showModal();
  fullPlayer.play().catch(() => {});
}
function stopPreviews() {
  gallery.querySelectorAll('video').forEach(v => {
    v.pause(); v.removeAttribute('src'); v.load(); v.classList.remove('playing');
  });
}
function makeCard(item) {
  const card = document.createElement('button'); card.type = 'button'; card.className = 'video-card';
  card.setAttribute('aria-label', `Watch ${item.filename}`);
  const frame = document.createElement('div'); frame.className = 'media-box';
  const thumb = document.createElement('img'); thumb.src = item.thumbnail_url; thumb.alt = '';
  thumb.loading = 'lazy';
  const preview = document.createElement('video'); preview.muted = true;
  preview.playsInline = true; preview.preload = 'none'; preview.controls = false;
  const playIcon = document.createElement('div'); playIcon.className = 'play-icon'; playIcon.textContent = '▶';
  const note = document.createElement('span'); note.className = 'preview-note'; note.textContent = '10s preview';
  frame.append(thumb, preview, playIcon, note);
  const info = document.createElement('div'); info.className = 'video-info';
  const name = document.createElement('p'); name.className = 'video-name'; name.textContent = item.filename;
  const meta = document.createElement('div'); meta.className = 'video-sub';
  const source = document.createElement('span'); source.textContent = item.producer;
  const size = document.createElement('span'); size.className = 'tag'; size.textContent = formatBytes(item.final_bytes);
  meta.append(source, size); info.append(name, meta); card.append(frame, info);
  let hoverTimer;
  function startPreview() {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      if (!card.isConnected || modal.open) return;
      preview.src = item.preview_url;
      preview.classList.add('playing');
      preview.play().catch(() => {preview.classList.remove('playing');});
    }, 170);
  }
  function endPreview() {
    clearTimeout(hoverTimer);
    preview.pause(); preview.removeAttribute('src'); preview.load(); preview.classList.remove('playing');
  }
  card.addEventListener('pointerenter', event => {if (event.pointerType !== 'touch') startPreview();});
  card.addEventListener('pointerleave', endPreview);
  card.addEventListener('blur', endPreview);
  preview.addEventListener('ended', endPreview);
  card.addEventListener('click', () => openPlayer(item));
  return card;
}
function paint() {
  stopPreviews(); gallery.replaceChildren();
  const items = videos.filter(v => `${v.filename} ${v.producer}`.toLowerCase().includes(selectedFilter));
  if (!items.length) {
    const empty = document.createElement('div'); empty.className = 'empty';
    empty.textContent = videos.length ? 'No videos match your filter.' : 'No processed videos yet. Run the producer to upload some!';
    gallery.append(empty); return;
  }
  for (const item of items) gallery.append(makeCard(item));
}
async function refresh() {
  try {
    const [videosResponse, statsResponse] = await Promise.all([
      fetch('/api/videos', {cache:'no-store'}), fetch('/api/stats', {cache:'no-store'})
    ]);
    if (!videosResponse.ok || !statsResponse.ok) throw new Error(`HTTP ${videosResponse.status}/${statsResponse.status}`);
    const [data, stats] = await Promise.all([videosResponse.json(), statsResponse.json()]);
    const signature = JSON.stringify(data.map(v => [v.id,v.final_bytes,v.status]));
    videos = data;
    if (signature !== lastSignature) { lastSignature = signature; paint(); }
    document.getElementById('ready-count').textContent = stats.ready_total;
    document.getElementById('queue-count').textContent = `${stats.queue_depth} / ${stats.queue_capacity}`;
    document.getElementById('workers-count').textContent = stats.active_workers;
    document.getElementById('drop-count').textContent = `${stats.dropped_this_run} / ${stats.duplicates_this_run}`;
    document.getElementById('health').textContent = 'Consumer online';
    document.getElementById('live-dot').classList.add('live');
  } catch (error) {
    document.getElementById('health').textContent = 'Consumer unavailable';
    document.getElementById('live-dot').classList.remove('live');
    if (!videos.length) {
      lastSignature = '';
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'Unable to load videos. Check consumer logs and network access.';
      gallery.replaceChildren(empty);
    }
    console.warn('Dashboard refresh failed', error);
  }
}
function closePlayer() {
  fullPlayer.pause(); fullPlayer.removeAttribute('src'); fullPlayer.load();
  if (modal.open) modal.close();
}
document.getElementById('refresh').addEventListener('click', refresh);
document.getElementById('close-player').addEventListener('click', closePlayer);
modal.addEventListener('close', () => { fullPlayer.pause(); fullPlayer.removeAttribute('src'); fullPlayer.load(); });
modal.addEventListener('click', event => {if (event.target === modal) closePlayer();});
search.addEventListener('input', event => {selectedFilter = event.target.value.trim().toLowerCase();paint();});
refresh(); setInterval(refresh, 4000);
