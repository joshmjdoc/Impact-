export const widgetRuntime = String.raw`
const scriptOrigin = new URL(document.currentScript?.src || location.href).origin;
class TurnWidget extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const root = this.attachShadow({ mode: 'open' });
    const status = document.createElement('span');
    status.textContent = 'Loading widget…';
    root.append(status);
    const key = this.getAttribute('widget-id') || this.dataset.widgetId;
    if (!key) return this.fail(root, 'Widget ID is missing.');
    fetch(scriptOrigin + '/api/public/widgets/' + encodeURIComponent(key))
      .then((response) => {
        if (!response.ok) throw new Error('unavailable');
        return response.json();
      })
      .then((config) => this.renderWidget(root, config))
      .catch(() => this.fail(root, 'This widget is temporarily unavailable.'));
  }
  fail(root, message) {
    root.replaceChildren();
    const messageNode = document.createElement('span');
    messageNode.setAttribute('role', 'status');
    messageNode.textContent = message;
    root.append(messageNode);
  }
  renderWidget(root, config) {
    root.replaceChildren();
    const style = document.createElement('style');
    style.textContent = ':host{font-family:system-ui,sans-serif}button{color:#fff;border:0;border-radius:14px;padding:14px 22px;font:600 16px system-ui;cursor:pointer}button:focus-visible{outline:3px solid #93c5fd;outline-offset:3px}.backdrop{position:fixed;inset:0;background:#102f28aa;display:grid;place-items:center;z-index:2147483647}.dialog{position:relative;background:#fff;width:min(920px,calc(100vw - 32px));height:min(760px,calc(100vh - 32px));border-radius:16px;overflow:hidden}.close{position:absolute;right:12px;top:10px;background:#173f36;width:40px;height:40px;padding:0;z-index:2}.frame{border:0;width:100%;height:100%}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}';
    const button = document.createElement('button');
    button.textContent = config.presentation.ctaLabel;
    button.style.backgroundColor = config.presentation.accent;
    button.addEventListener('click', () => this.launch(config));
    root.append(style, button);
  }
  launch(config) {
    if (config.launchMode === 'new_tab') {
      window.open(config.destinationUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    if (config.launchMode === 'modal') {
      this.openModal(config.destinationUrl);
      return;
    }
    window.location.assign(config.destinationUrl);
  }
  openModal(url) {
    const root = this.shadowRoot;
    const backdrop = document.createElement('div');
    backdrop.className = 'backdrop';
    const dialog = document.createElement('div');
    dialog.className = 'dialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-label', 'TelehealthUS secure experience');
    const close = document.createElement('button');
    close.className = 'close';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Close');
    const frame = document.createElement('iframe');
    frame.className = 'frame';
    frame.title = 'TelehealthUS secure experience';
    frame.src = url;
    const previousFocus = root.activeElement;
    const dismiss = () => { backdrop.remove(); previousFocus?.focus(); };
    close.addEventListener('click', dismiss);
    backdrop.addEventListener('click', (event) => { if (event.target === backdrop) dismiss(); });
    backdrop.addEventListener('keydown', (event) => { if (event.key === 'Escape') dismiss(); });
    dialog.append(close, frame); backdrop.append(dialog); root.append(backdrop); close.focus();
  }
}
if (!customElements.get('turn-widget')) customElements.define('turn-widget', TurnWidget);
document.querySelectorAll('[data-turn-widget]').forEach((node) => {
  if (node.tagName.toLowerCase() === 'turn-widget') return;
  const widget = document.createElement('turn-widget');
  widget.setAttribute('widget-id', node.getAttribute('data-turn-widget'));
  node.replaceWith(widget);
});
`;
