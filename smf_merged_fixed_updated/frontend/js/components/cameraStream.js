/**
 * frontend/js/components/cameraStream.js
 * ======================================
 * Biometric Face Recognition Video Stream Controller.
 * Manages MJPEG stream connection, network dropouts, reconnection timers, and snapshots.
 */

export class CameraStreamController {
  constructor(imgElementId, options = {}) {
    this.imgId = imgElementId;
    this.endpoint = options.endpoint || '/video_feed';
    this.retryDelay = options.retryDelay || 1500;
    this.retryTimer = null;
    this.isActive = false;
    this.onStateChange = options.onStateChange || null;
  }

  get element() {
    return document.getElementById(this.imgId);
  }

  /**
   * Start or attach live video stream
   */
  start() {
    const el = this.element;
    if (!el) return;

    this.isActive = true;
    el.src = `${this.endpoint}?t=${Date.now()}`;
    el.onerror = () => this.handleError();

    if (this.onStateChange) this.onStateChange(true);
  }

  /**
   * Stop video stream and release connection
   */
  stop() {
    this.isActive = false;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }

    const el = this.element;
    if (el) {
      el.src = '';
      el.onerror = null;
    }

    if (this.onStateChange) this.onStateChange(false);
  }

  /**
   * Resilient auto-retry on frame drop or MJPEG socket disconnect
   */
  handleError() {
    if (!this.isActive || this.retryTimer) return;

    console.warn('[CameraStream] Stream connection dropped, attempting reconnect...');
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      const el = this.element;
      if (el && this.isActive) {
        el.src = `${this.endpoint}?t=${Date.now()}`;
      }
    }, this.retryDelay);
  }

  /**
   * Capture still frame from live video feed into a canvas
   */
  captureSnapshot() {
    const el = this.element;
    if (!el || !this.isActive) return null;

    const canvas = document.createElement('canvas');
    canvas.width = el.naturalWidth || 640;
    canvas.height = el.naturalHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(el, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
  }
}

export default CameraStreamController;
