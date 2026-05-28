let ws = null;
let connected = false;

function connect() {
  try {
    ws = new WebSocket('ws://127.0.0.1:8765/ws/');
    ws.onopen = () => { connected = true; console.log('EEAM WS connected'); };
    ws.onclose = () => { connected = false; console.log('EEAM WS closed'); setTimeout(connect, 2000); };
    ws.onerror = (e) => { console.error('EEAM WS error', e); };
    ws.onmessage = (m) => { console.log('EEAM WS message', m.data); };
  } catch (e) {
    console.error('WS connect failed', e);
    setTimeout(connect, 2000);
  }
}

connect();

async function sendEvent(obj) {
  const payload = JSON.stringify(obj);
  if (connected && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(payload);
  } else {
    console.log('WS not connected, dropping event:', payload);
  }
}

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    sendEvent({ type: 'tab_activated', url: tab.url, title: tab.title, tabId: tab.id, timestamp: Date.now() });
  } catch (e) { console.error(e); }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' || changeInfo.url) {
    sendEvent({ type: 'tab_updated', url: tab.url, title: tab.title, tabId: tab.id, timestamp: Date.now() });
  }
});
