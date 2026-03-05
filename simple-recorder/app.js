const API_BASE = 'http://127.0.0.1:8765/api';

const FALLBACK_LINES = [
  'The quick brown fox jumps over the lazy dog.',
  'Hello, this is a sample line for voice recording.',
  'Please read this sentence clearly and at a steady pace.',
];

const lineTextEl = document.getElementById('line-text');
const lineInfoEl = document.getElementById('line-info');
const micSelectEl = document.getElementById('mic-select');
const btnPrev = document.getElementById('btn-prev');
const btnRecord = document.getElementById('btn-record');
const recordLabel = document.getElementById('record-label');
const afterRecord = document.getElementById('after-record');
const btnSave = document.getElementById('btn-save');
const btnRedo = document.getElementById('btn-redo');
const btnNext = document.getElementById('btn-next');
const statusEl = document.getElementById('status');

let scripts = [];
let allLines = [];
let scriptIndex = 0;
let lineIndex = 0;
let isRecording = false;
let mediaRecorder = null;
let stream = null;
let chunks = [];
let lastBlob = null;
let recordingKey = '';

function setStatus(msg, isError = false) {
  statusEl.textContent = msg || '';
  statusEl.classList.toggle('error', isError);
}

async function convertToWav(chunks) {
  const audioBlob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
  const arrayBuffer = await audioBlob.arrayBuffer();
  const audioContext = new AudioContext({ sampleRate: 22050 });
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  const samples = audioBuffer.getChannelData(0);
  const int16Samples = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    int16Samples[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const wavBuffer = new ArrayBuffer(44 + int16Samples.length * 2);
  const view = new DataView(wavBuffer);
  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + int16Samples.length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 22050, true);
  view.setUint32(28, 22050 * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, int16Samples.length * 2, true);
  new Int16Array(wavBuffer, 44).set(int16Samples);
  return new Blob([wavBuffer], { type: 'audio/wav' });
}

async function loadScripts() {
  try {
    const res = await fetch(`${API_BASE}/scripts`);
    if (!res.ok) throw new Error('Failed to load scripts');
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      scripts = data;
      allLines = [];
      scripts.forEach((s) => {
        (s.lines || []).forEach((line, i) => {
          allLines.push({
            text: line,
            scriptName: s.name,
            lineNum: i + 1,
            totalInScript: (s.lines || []).length,
          });
        });
      });
      if (allLines.length > 0) return;
    }
  } catch (_) {}
  allLines = FALLBACK_LINES.map((text, i) => ({
    text,
    scriptName: 'sample',
    lineNum: i + 1,
    totalInScript: FALLBACK_LINES.length,
  }));
}

async function loadMics() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const mics = devices.filter((d) => d.kind === 'audioinput');
    micSelectEl.innerHTML = '<option value="">Default microphone</option>';
    mics.forEach((d) => {
      const opt = document.createElement('option');
      opt.value = d.deviceId;
      opt.textContent = d.label || `Microphone ${micSelectEl.options.length}`;
      micSelectEl.appendChild(opt);
    });
  } catch (e) {
    setStatus('Could not list microphones', true);
  }
}

function getCurrentLine() {
  return allLines[lineIndex] || null;
}

function updateUI() {
  const line = getCurrentLine();
  if (line) {
    lineTextEl.textContent = line.text;
    lineInfoEl.textContent = `Line ${line.lineNum} of ${line.totalInScript} · ${line.scriptName}`;
  } else {
    lineTextEl.textContent = 'No lines.';
    lineInfoEl.textContent = '—';
  }
  btnPrev.disabled = lineIndex === 0;
  btnNext.disabled = lineIndex >= allLines.length - 1;
}

function buildRecordingKey() {
  const line = getCurrentLine();
  if (!line) return '';
  const num = String(line.lineNum).padStart(4, '0');
  return `${line.scriptName}_${num}`;
}

async function startRecording() {
  const deviceId = micSelectEl.value || undefined;
  try {
    const constraints = {
      audio: deviceId ? { deviceId: { exact: deviceId } } : true,
    };
    stream = await navigator.mediaDevices.getUserMedia(constraints);
    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
    mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
    chunks = [];
    mediaRecorder.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      if (chunks.length > 0) lastBlob = await convertToWav(chunks);
      afterRecord.classList.remove('hidden');
      setStatus('Recording stopped. Save or Redo.');
    };
    mediaRecorder.start(100);
    isRecording = true;
    btnRecord.classList.add('recording');
    recordLabel.textContent = 'Stop';
    afterRecord.classList.add('hidden');
    setStatus('Recording…');
  } catch (e) {
    setStatus('Microphone access denied or failed.', true);
  }
}

function stopRecording() {
  if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
  mediaRecorder.stop();
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  mediaRecorder = null;
  isRecording = false;
  btnRecord.classList.remove('recording');
  recordLabel.textContent = 'Record';
  setStatus('');
}

async function saveRecording() {
  if (!lastBlob) return;
  recordingKey = buildRecordingKey();
  const filename = `${recordingKey}.wav`;
  const formData = new FormData();
  formData.append('audio_file', lastBlob, filename);
  formData.append('filename', filename);
  formData.append('gain', '1.0');
  try {
    const res = await fetch(`${API_BASE}/recording/save`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Save failed');
    }
    setStatus('Saved.');
    lastBlob = null;
    afterRecord.classList.add('hidden');
    setTimeout(() => setStatus(''), 2000);
  } catch (e) {
    setStatus(e.message || 'Could not save to server.', true);
  }
}

function redoRecording() {
  lastBlob = null;
  afterRecord.classList.add('hidden');
  setStatus('Redo. Record again when ready.');
}

function prevLine() {
  if (lineIndex > 0) {
    lineIndex--;
    lastBlob = null;
    afterRecord.classList.add('hidden');
    updateUI();
    setStatus('');
  }
}

function nextLine() {
  if (lineIndex < allLines.length - 1) {
    lineIndex++;
    lastBlob = null;
    afterRecord.classList.add('hidden');
    updateUI();
    setStatus('');
  }
}

btnRecord.addEventListener('click', () => {
  if (isRecording) stopRecording();
  else startRecording();
});

btnSave.addEventListener('click', saveRecording);
btnRedo.addEventListener('click', redoRecording);
btnPrev.addEventListener('click', prevLine);
btnNext.addEventListener('click', nextLine);

(async function init() {
  setStatus('Loading…');
  await loadScripts();
  await loadMics();
  lineIndex = 0;
  updateUI();
  setStatus('');
})();
