document.addEventListener('DOMContentLoaded', () => {
  const wsStatus = document.getElementById('ws-status');
  const wsConnectBtn = document.getElementById('ws-connect');
  const wsDisconnectBtn = document.getElementById('ws-disconnect');
  const apiKeyInput = document.getElementById('api-key');
  const messageInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');
  const responseContainer = document.getElementById('ws-response');
  
  let ws = null;
  
  // WebSocket connection
  wsConnectBtn.addEventListener('click', () => {
    const apiKey = apiKeyInput.value.trim();
    
    if (!apiKey) {
      alert('لطفا API Key را وارد کنید');
      return;
    }
    
    // Replace with your actual WebSocket URL
    ws = new WebSocket(`ws://${window.location.host}/ws/v1/chat/completions`);
    
    ws.onopen = () => {
      wsStatus.textContent = 'متصل';
      wsStatus.className = 'status-connected';
      
      // Send authentication first
      ws.send(JSON.stringify({
        api_key: apiKey
      }));
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Create message element
        const messageEl = document.createElement('div');
        messageEl.className = 'message';
        
        if (data.choices && data.choices[0] && data.choices[0].delta && data.choices[0].delta.content) {
          messageEl.textContent = data.choices[0].delta.content;
        } else if (data.error) {
          messageEl.textContent = `خطا: ${data.error}`;
          messageEl.className = 'message error';
        } else {
          messageEl.textContent = JSON.stringify(data, null, 2);
        }
        
        responseContainer.appendChild(messageEl);
        responseContainer.scrollTop = responseContainer.scrollHeight;
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      wsStatus.textContent = 'خطا در اتصال';
      wsStatus.className = 'status-error';
    };
    
    ws.onclose = () => {
      wsStatus.textContent = 'قطع ارتباط';
      wsStatus.className = 'status-disconnected';
    };
  });
  
  // Disconnect WebSocket
  wsDisconnectBtn.addEventListener('click', () => {
    if (ws) {
      ws.close();
      ws = null;
    }
  });
  
  // Send message
  sendBtn.addEventListener('click', () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      alert('ابتدا به WebSocket متصل شوید');
      return;
    }
    
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Send chat configuration and message
    ws.send(JSON.stringify({
      model: "openai/gpt-4o-mini",
      messages: [{
        role: "user",
        content: message
      }],
      stream: true
    }));
    
    // Clear input
    messageInput.value = '';
  });
  
  // Send on Enter key
  messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      sendBtn.click();
    }
  });
});
