document.addEventListener('DOMContentLoaded', () => {
  const wsStatus = document.getElementById('ws-status');
  const wsConnectBtn = document.getElementById('ws-connect');
  const wsDisconnectBtn = document.getElementById('ws-disconnect');
  const apiKeyInput = document.getElementById('api-key');
  const messageInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');
  const responseContainer = document.getElementById('ws-response');
  
  let ws = null;
  let currentMessageStreamElement = null;

  function updateWsStatus(message, isError = false, isConnected = false) {
    // wsStatus.textContent = `وضعیت: ${message}`; // Original Persian
    wsStatus.textContent = `Status: ${message}`; // Translated
    wsStatus.classList.remove('bg-green-700', 'text-green-100', 'bg-red-700', 'text-red-100', 'bg-yellow-700', 'text-yellow-100', 'bg-gray-700', 'text-gray-300');
    if (isConnected) {
        wsStatus.classList.add('bg-green-700', 'text-green-100'); // Connected
    } else if (isError) {
        wsStatus.classList.add('bg-red-700', 'text-red-100'); // Error
    } else {
        wsStatus.classList.add('bg-gray-700', 'text-gray-300'); // Default / Disconnected
    }
  }

  function setUIConnected(connected) {
    wsConnectBtn.disabled = connected;
    wsDisconnectBtn.disabled = !connected;
    apiKeyInput.disabled = connected;
    messageInput.disabled = !connected;
    sendBtn.disabled = !connected;
  }

  // Initial UI State
  setUIConnected(false);
  // updateWsStatus('قطع'); // Original Persian: Disconnected
  updateWsStatus('Disconnected'); // Translated
  
  // WebSocket connection
  wsConnectBtn.addEventListener('click', () => {
    let apiKey = apiKeyInput.value.trim();
    
    if (!apiKey) {
      // alert('لطفا API Key را وارد کنید'); // Original Persian
      alert('Please enter your API Key.'); // Translated
      return;
    }

    if (!apiKey.toLowerCase().startsWith('bearer ')) {
        apiKey = `Bearer ${apiKey}`;
    }
    
    // responseContainer.innerHTML = '<p class="text-gray-500">در حال اتصال...</p>'; // Original Persian: Connecting...
    responseContainer.innerHTML = '<p class="text-gray-500">Connecting...</p>'; // Translated
    currentMessageStreamElement = null;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/v1/chat/completions`);
    // updateWsStatus('در حال اتصال...'); // Original Persian: Connecting...
    updateWsStatus('Connecting...'); // Translated
    
    ws.onopen = () => {
      setUIConnected(true);
      // updateWsStatus('متصل', false, true); // Original Persian: Connected
      updateWsStatus('Connected', false, true); // Translated
      
      ws.send(JSON.stringify({ api_key: apiKey }));
      // responseContainer.innerHTML = '<p class="text-green-400">اتصال برقرار شد. می‌توانید پیام ارسال کنید.</p>'; // Original Persian: Connection established. You can send messages.
      responseContainer.innerHTML = '<p class="text-green-400">Connection established. You can send messages.</p>'; // Translated
    };
    
    ws.onmessage = (event) => {
        // Clear initial status messages like "Connecting...", "Connected", "Error" etc.
        // The Persian strings were: "پاسخ‌ها اینجا نمایش داده می‌شوند", "در حال اتصال", "اتصال برقرار شد", "خطا"
        // Corresponding English: "Responses will be shown here...", "Connecting...", "Connection established", "Error"
        if (responseContainer.querySelector('.text-gray-500, .text-green-400, .text-red-400')) {
            if (responseContainer.innerHTML.includes("Responses will be shown here...") || // HTML was already updated
                responseContainer.innerHTML.includes("Connecting...") ||
                responseContainer.innerHTML.includes("Connection established.") || // Matched to new message
                responseContainer.innerHTML.includes("Error")) { // Assuming generic "Error" might appear
                responseContainer.innerHTML = '';
            }
        }

        try {
            const data = JSON.parse(event.data);
            let messageText = '';
            let isError = false;

            if (data.error) {
                // messageText = `خطا: ${data.error}`; // Original Persian: Error:
                messageText = `Error: ${data.error}`; // Translated
                isError = true;
                currentMessageStreamElement = null;
            } else if (data.choices && data.choices[0] && data.choices[0].delta && typeof data.choices[0].delta.content === 'string') {
                messageText = data.choices[0].delta.content;
            } else if (data.choices && data.choices[0] && data.choices[0].message && typeof data.choices[0].message.content === 'string') {
                messageText = data.choices[0].message.content;
                currentMessageStreamElement = null;
            } else {
                messageText = JSON.stringify(data, null, 2);
                currentMessageStreamElement = null;
            }

            if (messageText) {
                if (!isError && data.choices && data.choices[0] && data.choices[0].delta) {
                    if (!currentMessageStreamElement) {
                        currentMessageStreamElement = document.createElement('div');
                        currentMessageStreamElement.classList.add('text-gray-200', 'p-2', 'my-1', 'rounded', 'bg-gray-600', 'whitespace-pre-wrap');
                        responseContainer.appendChild(currentMessageStreamElement);
                    }
                    currentMessageStreamElement.textContent += messageText;
                } else {
                    const messageEl = document.createElement('div');
                    messageEl.classList.add('p-2', 'my-1', 'rounded', 'whitespace-pre-wrap');
                    messageEl.textContent = messageText;
                    if (isError) {
                        messageEl.classList.add('text-red-400', 'bg-red-900', 'bg-opacity-30');
                    } else {
                        messageEl.classList.add('text-gray-200', 'bg-gray-600');
                    }
                    responseContainer.appendChild(messageEl);
                    currentMessageStreamElement = null;
                }
            }

            responseContainer.scrollTop = responseContainer.scrollHeight;
        } catch (e) {
            console.error('Error processing WebSocket message:', e, 'Raw data:', event.data);
            if (event.data && event.data.trim() !== "") {
                const errorDisplay = document.createElement('div');
                errorDisplay.classList.add('text-red-400', 'bg-red-900', 'bg-opacity-30', 'p-2', 'my-1', 'rounded', 'whitespace-pre-wrap');
                // errorDisplay.textContent = `خطا در پردازش پیام: ${event.data}`; // Original Persian: Error processing message:
                errorDisplay.textContent = `Error processing message: ${event.data}`; // Translated
                responseContainer.appendChild(errorDisplay);
                responseContainer.scrollTop = responseContainer.scrollHeight;
            }
        }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      // updateWsStatus('خطا در اتصال', true); // Original Persian: Error in connection
      updateWsStatus('Connection Error', true); // Translated
      setUIConnected(false);
      // responseContainer.innerHTML = `<p class="text-red-400">خطا در اتصال WebSocket. جزئیات در کنسول مرورگر.</p>`; // Original Persian
      responseContainer.innerHTML = `<p class="text-red-400">WebSocket connection error. See browser console for details.</p>`; // Translated
      currentMessageStreamElement = null;
    };
    
    ws.onclose = (event) => {
      // updateWsStatus(`قطع (کد: ${event.code})`); // Original Persian: Disconnected (code: ...)
      updateWsStatus(`Disconnected (Code: ${event.code})`); // Translated
      setUIConnected(false);
      if (!event.wasClean && event.code !== 1000) {
          // responseContainer.innerHTML = `<p class="text-yellow-400">اتصال به طور غیرمنتظره قطع شد (کد: ${event.code}).</p>`; // Original Persian
          responseContainer.innerHTML = `<p class="text-yellow-400">Connection closed unexpectedly (Code: ${event.code}).</p>`; // Translated
      // } else if (responseContainer.innerHTML.includes("اتصال برقرار شد")) { // Original Persian: Connection established.
      } else if (responseContainer.innerHTML.includes("Connection established.")) { // Translated
          // responseContainer.innerHTML = '<p class="text-gray-500">ارتباط قطع شد.</p>'; // Original Persian: Connection closed.
          responseContainer.innerHTML = '<p class="text-gray-500">Connection closed.</p>'; // Translated
      }
      currentMessageStreamElement = null;
    };
  });
  
  wsDisconnectBtn.addEventListener('click', () => {
    if (ws) {
      ws.close(1000, "User disconnected");
    }
    setUIConnected(false);
    // updateWsStatus('قطع'); // Original Persian: Disconnected
    updateWsStatus('Disconnected'); // Translated
    // responseContainer.innerHTML = '<p class="text-gray-500">پاسخ‌ها اینجا نمایش داده می‌شوند...</p>'; // Original Persian
    responseContainer.innerHTML = '<p class="text-gray-500">Responses will be shown here...</p>'; // Translated (already done in HTML)
    currentMessageStreamElement = null;
  });
  
  sendBtn.addEventListener('click', () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      // alert('ابتدا به WebSocket متصل شوید'); // Original Persian
      alert('Please connect to WebSocket first.'); // Translated
      return;
    }
    
    const message = messageInput.value.trim();
    if (!message) return;
    
    ws.send(JSON.stringify({
      model: "openai/gpt-4o-mini",
      messages: [{
        role: "user",
        content: message
      }],
      stream: true
    }));
    
    messageInput.value = '';
  });
  
  messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      sendBtn.click();
    }
  });

  $('.copy-btn').on('click', function() {
    const codeBlock = $(this).siblings('pre').find('code');

    if (codeBlock.length === 0) {
        // alert('خطا: بلوک کد برای کپی یافت نشد.'); // Original Persian
        alert('Error: Code block for copying not found.'); // Translated
        return;
    }

    const textToCopy = codeBlock.text();

    // The original text for the button is now "Copy" from the HTML.
    // const originalText = $(this).text(); // This would be "Copy"
    const originalText = "Copy"; // Explicitly set, as HTML is already "Copy"

    navigator.clipboard.writeText(textToCopy).then(() => {
      // $(this).text('کپی شد!'); // Original Persian: Copied!
      $(this).text('Copied!'); // Translated
      setTimeout(() => {
        $(this).text(originalText);
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy text: ', err);
      // alert('خطا در کپی متن. ممکن است نیاز به مجوز دسترسی به کلیپ‌بورد باشد یا در محیط ناامن (غیر HTTPS) اجرا شده باشد.'); // Original Persian
      alert('Error copying text. Clipboard access may be denied or page is insecure (non-HTTPS).'); // Translated
    });
  });

});
