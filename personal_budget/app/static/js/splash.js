(() => {
  const DURATION_MS = 3000;
  const FIRST_IMAGE_SRC = '/static/img/lf-software.png';
  const SECOND_IMAGE_SRC = '/static/img/budget-personal.png';
  const SPLASH_STORAGE_KEY = 'personal_budget_splash_seen_v1';

  function createStage(src, alt, darkBackground) {
    const stage = document.createElement('div');
    stage.className = `app-splash-stage${darkBackground ? ' app-splash-stage--dark' : ''}`;

    const img = document.createElement('img');
    img.className = 'app-splash-image';
    img.src = src;
    img.alt = alt;
    stage.appendChild(img);
    return stage;
  }

  async function preloadImage(src) {
    const img = new Image();
    img.src = src;
    if (img.decode) {
      try {
        await img.decode();
      } catch (_) {
        // Ignore decode failures and continue.
      }
    }
    return img;
  }

  function hasSeenSplash() {
    try {
      return window.localStorage.getItem(SPLASH_STORAGE_KEY) === '1';
    } catch (_) {
      return false;
    }
  }

  function markSplashAsSeen() {
    try {
      window.localStorage.setItem(SPLASH_STORAGE_KEY, '1');
    } catch (_) {
      // Ignore storage failures and continue.
    }
  }

  async function runSplash() {
    if (hasSeenSplash()) return;
    markSplashAsSeen();

    window.__appSplashRunning = true;
    document.body.classList.add('app-splash-running');

    await Promise.all([preloadImage(FIRST_IMAGE_SRC), preloadImage(SECOND_IMAGE_SRC)]);

    const container = document.createElement('div');
    container.className = 'app-splash-container';

    const stage1 = createStage(FIRST_IMAGE_SRC, 'LF Software', false);
    const stage2 = createStage(SECOND_IMAGE_SRC, 'Budget Personal', true);

    container.appendChild(stage1);
    container.appendChild(stage2);
    document.body.appendChild(container);

    stage1.classList.add('is-active');

    window.setTimeout(() => {
      stage1.classList.remove('is-active');
      stage2.classList.add('is-active');
    }, DURATION_MS);

    window.setTimeout(() => {
      stage2.classList.remove('is-active');
      container.remove();
      window.__appSplashRunning = false;
      document.body.classList.remove('app-splash-running');
      document.dispatchEvent(new CustomEvent('app-splash:end'));
    }, DURATION_MS * 2);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runSplash);
  } else {
    runSplash();
  }
})();
