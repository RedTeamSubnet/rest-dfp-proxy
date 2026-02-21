/**
 * Miner Testing Sandbox - Frontend Controller
 * Handles script execution, fingerprint collection, and result display
 */

(function() {
    'use strict';

    // DOM Elements
    const sessionIdInput = document.getElementById('session-id');
    const deviceLabelInput = document.getElementById('device-label');
    const submitBtn = document.getElementById('submit-btn');
    const resultsBtn = document.getElementById('results-btn');
    const statusDiv = document.getElementById('status');
    const resultsArea = document.getElementById('results-area');
    const sandbox = document.getElementById('sandbox');

    // State
    let isRunning = false;

    /**
     * Show status message
     */
    function showStatus(message, isError = false) {
        statusDiv.textContent = message;
        statusDiv.className = isError ? 'error' : 'success';
    }

    /**
     * Hide status message
     */
    function hideStatus() {
        statusDiv.className = '';
        statusDiv.style.display = 'none';
    }

    /**
     * Validate inputs
     */
    function validateInputs() {
        const sessionId = sessionIdInput.value.trim();
        const deviceLabel = deviceLabelInput.value.trim();

        if (!sessionId) {
            showStatus('Please enter a Session ID', true);
            return null;
        }
        if (!deviceLabel) {
            showStatus('Please enter a Device Label', true);
            return null;
        }

        return { sessionId, deviceLabel };
    }

    /**
     * Fetch fingerprinter.js from server
     */
    async function fetchFingerprinterJs() {
        const response = await fetch('/static/js/fingerprinter.js');
        if (!response.ok) {
            throw new Error('Failed to load fingerprinter.js');
        }
        return response.text();
    }

    /**
     * Execute fingerprint script in sandboxed iframe
     * Uses sandbox="allow-scripts" for isolation (no allow-same-origin)
     */
    function executeInSandbox(fingerprintJs) {
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                reject(new Error('Script execution timed out (5s limit)'));
            }, 5000);

            // Handle messages from sandbox
            function handleMessage(event) {
                // Only accept messages from our sandbox
                if (event.source !== sandbox.contentWindow) return;

                clearTimeout(timeoutId);
                window.removeEventListener('message', handleMessage);

                if (event.data && event.data.type === 'fingerprint-result') {
                    if (event.data.error) {
                        reject(new Error(event.data.error));
                    } else {
                        resolve(event.data.hash);
                    }
                }
            }

            window.addEventListener('message', handleMessage);

            // Create sandbox HTML with the script
            const sandboxHtml = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script>
        // Override eval for security
        window.eval = function() {
            throw new Error('eval() is not allowed');
        };

        // Prevent access to parent
        try {
            window.parent = null;
            window.top = null;
        } catch(e) {}
    </script>
</head>
<body>
    <script type="module">
        // User's fingerprint script
        try {
            ${fingerprintJs}

            // Execute and get result
            if (typeof runFingerprinting !== 'function') {
                throw new Error('runFingerprinting() function not found in fingerprinter.js');
            }

            runFingerprinting().then(result => {
                if (typeof result !== 'string') {
                    throw new Error('runFingerprinting() must return a string');
                }

                // Send result back to parent
                window.parent.postMessage({
                    type: 'fingerprint-result',
                    hash: result
                }, '*');
            }).catch(error => {
                window.parent.postMessage({
                    type: 'fingerprint-result',
                    error: error.message
                }, '*');
            });
        } catch (error) {
            window.parent.postMessage({
                type: 'fingerprint-result',
                error: error.message
            }, '*');
        }
    </script>
</body>
</html>`;

            // Load into sandbox
            const blob = new Blob([sandboxHtml], { type: 'text/html' });
            sandbox.src = URL.createObjectURL(blob);
        });
    }

    /**
     * Submit fingerprint to backend
     */
    async function submitFingerprint(sessionId, deviceLabel, fingerprintHash) {
        const response = await fetch('/collect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                device_label: deviceLabel,
                fingerprint_hash: fingerprintHash
            })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: 'Unknown error' }));
            throw new Error(error.message || `HTTP ${response.status}`);
        }

        return response.json();
    }

    /**
     * Fetch and display results
     */
    async function fetchResults(sessionId) {
        const response = await fetch(`/results?session_id=${encodeURIComponent(sessionId)}`);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: 'Unknown error' }));
            throw new Error(error.message || `HTTP ${response.status}`);
        }

        const data = await response.json();
        return data.data; // Response is wrapped in BaseResponse
    }

    /**
     * Display results in the UI
     */
    function displayResults(results) {
        // Update score
        document.getElementById('score-value').textContent = results.score;

        // Update breakdown
        document.getElementById('correct-count').textContent = results.breakdown.correct;
        document.getElementById('collision-count').textContent = results.breakdown.collisions;
        document.getElementById('fragmentation-count').textContent = results.breakdown.fragmentations;

        // Update devices list
        const devicesList = document.getElementById('devices-list');
        if (results.devices && results.devices.length > 0) {
            devicesList.innerHTML = results.devices.map((device, index) => `
                <div class="device-item">
                    <strong>#${index + 1}</strong> |
                    Label: <code>${escapeHtml(device.device_label)}</code> |
                    Hash: <code>${escapeHtml(device.fingerprint_hash)}</code>
                </div>
            `).join('');
        } else {
            devicesList.innerHTML = '<div class="device-item">No devices collected yet</div>';
        }

        // Show results area
        resultsArea.classList.add('active');
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Handle Submit button click
     */
    async function handleSubmit() {
        if (isRunning) return;

        const inputs = validateInputs();
        if (!inputs) return;

        isRunning = true;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Running...';
        hideStatus();

        try {
            // Fetch fingerprinter.js from server
            showStatus('Loading fingerprinter.js...');
            const fingerprintJs = await fetchFingerprinterJs();

            // Execute script in sandbox
            showStatus('Executing script in sandbox...');
            const fingerprintHash = await executeInSandbox(fingerprintJs);

            // Submit to backend
            showStatus('Submitting fingerprint...');
            await submitFingerprint(inputs.sessionId, inputs.deviceLabel, fingerprintHash);

            showStatus(`✓ Fingerprint collected: ${fingerprintHash.substring(0, 32)}...`);

        } catch (error) {
            showStatus(`✗ Error: ${error.message}`, true);
        } finally {
            isRunning = false;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Fingerprint';
        }
    }

    /**
     * Handle Results button click
     */
    async function handleResults() {
        const sessionId = sessionIdInput.value.trim();

        if (!sessionId) {
            showStatus('Please enter a Session ID first', true);
            return;
        }

        resultsBtn.disabled = true;
        resultsBtn.textContent = 'Loading...';
        hideStatus();

        try {
            showStatus('Fetching results...');
            const results = await fetchResults(sessionId);
            displayResults(results);
            showStatus('✓ Results loaded successfully');
        } catch (error) {
            showStatus(`✗ Error: ${error.message}`, true);
        } finally {
            resultsBtn.disabled = false;
            resultsBtn.textContent = 'View Results';
        }
    }

    // Event listeners
    submitBtn.addEventListener('click', handleSubmit);
    resultsBtn.addEventListener('click', handleResults);

    // Allow Enter key to submit
    sessionIdInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSubmit();
    });
    deviceLabelInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSubmit();
    });

    console.log('Miner Testing Sandbox initialized');
})();
