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
    wsStatus.textContent = `وضعیت: ${message}`;
    // Remove old Tailwind classes related to status color, then add new ones
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
  updateWsStatus('قطع');
  
  // WebSocket connection
  wsConnectBtn.addEventListener('click', () => {
    let apiKey = apiKeyInput.value.trim();
    
    if (!apiKey) {
      alert('لطفا API Key را وارد کنید');
      return;
    }

    if (!apiKey.toLowerCase().startsWith('bearer ')) {
        apiKey = `Bearer ${apiKey}`;
    }
    
    responseContainer.innerHTML = '<p class="text-gray-500">در حال اتصال...</p>'; // Clear previous messages
    currentMessageStreamElement = null; // Reset stream element

    // Ensure correct WebSocket protocol (ws or wss)
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/v1/chat/completions`);
    updateWsStatus('در حال اتصال...');
    
    ws.onopen = () => {
      setUIConnected(true);
      updateWsStatus('متصل', false, true);
      
      ws.send(JSON.stringify({ api_key: apiKey }));
      // Optionally, clear the initial "در حال اتصال..." message or add a "Connected" message
      responseContainer.innerHTML = '<p class="text-green-400">اتصال برقرار شد. می‌توانید پیام ارسال کنید.</p>';
    };
    
    ws.onmessage = (event) => {
        if (responseContainer.querySelector('.text-gray-500, .text-green-400, .text-red-400')) {
             // Clear initial status messages like "Connecting...", "Connected", "Error"
            if (responseContainer.innerHTML.includes("پاسخ‌ها اینجا نمایش داده می‌شوند") ||
                responseContainer.innerHTML.includes("در حال اتصال") ||
                responseContainer.innerHTML.includes("اتصال برقرار شد") ||
                responseContainer.innerHTML.includes("خطا")) {
                responseContainer.innerHTML = '';
            }
        }

        try {
            const data = JSON.parse(event.data);
            let messageText = '';
            let isError = false;

            if (data.error) {
                messageText = `خطا: ${data.error}`;
                isError = true;
                currentMessageStreamElement = null; // Stop appending to any previous stream
            } else if (data.choices && data.choices[0] && data.choices[0].delta && typeof data.choices[0].delta.content === 'string') {
                messageText = data.choices[0].delta.content;
            } else if (data.choices && data.choices[0] && data.choices[0].message && typeof data.choices[0].message.content === 'string') { // Non-streamed full response
                messageText = data.choices[0].message.content;
                currentMessageStreamElement = null;
            } else {
                // Fallback for other JSON structures or if no content/error
                messageText = JSON.stringify(data, null, 2);
                currentMessageStreamElement = null;
            }

            if (messageText) {
                if (!isError && data.choices && data.choices[0] && data.choices[0].delta) { // It's a stream chunk
                    if (!currentMessageStreamElement) {
                        currentMessageStreamElement = document.createElement('div');
                        currentMessageStreamElement.classList.add('text-gray-200', 'p-2', 'my-1', 'rounded', 'bg-gray-600', 'whitespace-pre-wrap');
                        responseContainer.appendChild(currentMessageStreamElement);
                    }
                    currentMessageStreamElement.textContent += messageText;
                } else { // Full message or error
                    const messageEl = document.createElement('div');
                    messageEl.classList.add('p-2', 'my-1', 'rounded', 'whitespace-pre-wrap');
                    messageEl.textContent = messageText;
                    if (isError) {
                        messageEl.classList.add('text-red-400', 'bg-red-900', 'bg-opacity-30');
                    } else {
                        messageEl.classList.add('text-gray-200', 'bg-gray-600');
                    }
                    responseContainer.appendChild(messageEl);
                    currentMessageStreamElement = null; // Reset for next full message
                }
            }

            responseContainer.scrollTop = responseContainer.scrollHeight;
        } catch (e) {
            console.error('Error processing WebSocket message:', e, 'Raw data:', event.data);
            // Display raw data if JSON parsing fails and it's not an empty string
            if (event.data && event.data.trim() !== "") {
                const errorDisplay = document.createElement('div');
                errorDisplay.classList.add('text-red-400', 'bg-red-900', 'bg-opacity-30', 'p-2', 'my-1', 'rounded', 'whitespace-pre-wrap');
                errorDisplay.textContent = `خطا در پردازش پیام: ${event.data}`;
                responseContainer.appendChild(errorDisplay);
                responseContainer.scrollTop = responseContainer.scrollHeight;
            }
        }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      updateWsStatus('خطا در اتصال', true);
      setUIConnected(false);
      responseContainer.innerHTML = `<p class="text-red-400">خطا در اتصال WebSocket. جزئیات در کنسول مرورگر.</p>`;
      currentMessageStreamElement = null;
    };
    
    ws.onclose = (event) => {
      updateWsStatus(`قطع (کد: ${event.code})`);
      setUIConnected(false);
      if (!event.wasClean && event.code !== 1000) { // 1000 is normal closure
          responseContainer.innerHTML = `<p class="text-yellow-400">اتصال به طور غیرمنتظره قطع شد (کد: ${event.code}).</p>`;
      } else if (responseContainer.innerHTML.includes("اتصال برقرار شد")) {
          // If only "Connected" message was there, replace it or add to it
          responseContainer.innerHTML = '<p class="text-gray-500">ارتباط قطع شد.</p>';
      }
      currentMessageStreamElement = null;
    };
  });
  
  // Disconnect WebSocket
  wsDisconnectBtn.addEventListener('click', () => {
    if (ws) {
      ws.close(1000, "User disconnected"); // Send a normal closure code
    }
    setUIConnected(false); // Explicitly set UI state on manual disconnect
    updateWsStatus('قطع');
    responseContainer.innerHTML = '<p class="text-gray-500">پاسخ‌ها اینجا نمایش داده می‌شوند...</p>';
    currentMessageStreamElement = null;
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

  // Copy to clipboard for code blocks
  $('.copy-btn').on('click', function() {
    console.log("Copy button clicked", this);
    const codeBlock = $(this).siblings('pre').find('code');
    console.log("Found code block element:", codeBlock.get(0)); // Log the DOM element

    if (codeBlock.length === 0) {
        console.error("Could not find code block for button:", this);
        alert('خطا: بلوک کد برای کپی یافت نشد.');
        return;
    }

    const textToCopy = codeBlock.text();
    console.log("Text to copy:", textToCopy);

    if (!textToCopy.trim()) {
        console.warn("Attempting to copy empty or whitespace-only text.");
        // Optionally alert the user or just do nothing
        // alert('محتوایی برای کپی وجود ندارد.');
        // return;
    }

    navigator.clipboard.writeText(textToCopy).then(() => {
      const originalText = $(this).text();
      $(this).text('کپی شد!');
      console.log('Text copied successfully!');
      setTimeout(() => {
        $(this).text(originalText);
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy text: ', err);
      alert('خطا در کپی متن. ممکن است نیاز به مجوز دسترسی به کلیپ‌بورد باشد یا در محیط ناامن (غیر HTTPS) اجرا شده باشد.');
    });
  });

});
