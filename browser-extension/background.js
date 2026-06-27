let ws = null;

function ensureWS() {
  try {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    ws = new WebSocket('ws://127.0.0.1:8585');
    ws.onopen = () => console.log('EM WS connected');
    ws.onclose = () => { console.log('EM WS closed'); setTimeout(ensureWS, 2000); };
    ws.onerror = (e) => console.warn('EM WS error', e);
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
