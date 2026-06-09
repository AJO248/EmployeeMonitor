let ws = null;

function ensureWS() {
  try {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    ws = new WebSocket('ws://127.0.0.1:8585');
    ws.onopen = () => console.log('CPAM WS connected');
    ws.onclose = () => { console.log('CPAM WS closed'); setTimeout(ensureWS, 2000); };
    ws.onerror = (e) => console.warn('CPAM WS error', e);
  } catch (e) {
    console.warn('WS init failed', e);
    setTimeout(ensureWS, 2000);
  }
}

ensureWS();

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    const payload = { type: 'tab_activated', url: tab.url, title: tab.title, timestamp: Date.now() };
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  } catch (e) {
    console.error(e);
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') {
    const payload = { type: 'tab_updated', url: tab.url, title: tab.title, timestamp: Date.now() };
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  }
});
