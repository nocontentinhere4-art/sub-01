// Renders storyboard.html frame by frame (deterministic seek) and encodes an MP4 for X.
// usage: node render.js [fps]
const path = require('path'), fs = require('fs'), { execFileSync } = require('child_process');
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const FPS = +(process.argv[2] || 30);
const dir = __dirname, frames = path.join(dir, 'frames');
(async () => {
  fs.rmSync(frames, { recursive: true, force: true }); fs.mkdirSync(frames);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1080 } });
  await page.goto('file://' + path.join(dir, 'storyboard.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(800);
  const dur = await page.evaluate(() => window.DUR);
  const n = Math.round(dur * FPS);
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.seek(t), i / FPS);
    await page.screenshot({ path: path.join(frames, String(i).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 95 });
    if (i % 90 === 0) console.log(`frame ${i}/${n}`);
  }
  await browser.close();
  execFileSync('python3', [path.join(dir, 'soundtrack.py'), String(dur)], { stdio: 'inherit' });
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(frames, '%05d.jpg'),
    '-i', path.join(dir, 'soundtrack.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
    '-profile:v', 'high', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
    path.join(dir, 'sub01_x_launch.mp4')], { stdio: 'inherit' });
  console.log('done');
})();
