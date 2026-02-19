async function sendFingerprint(payload) {
	const response = await fetch(window.ENDPOINT, {
		method: "POST",
		body: JSON.stringify(payload),
		headers: {
			"Content-Type": "application/json",
			Accept: "application/json",
		},
	});

	if (!response.ok) {
		throw new Error(`HTTP error! status: ${response.status}`);
	}

	return response.json();
}

export async function postProcess(fingerprint) {
	console.log("[PostProcess] Cleaning up environment...");

	try {
		const payload = {
			fingerprint,
			order_id: window.ORDER_ID || "unknown",
		};
		await sendFingerprint(payload);
	} catch (error) {
		console.error("[PostProcess] Error sending fingerprint:", error);
		throw error;
	}

	// Overwrite or delete global variables used
	try {
		delete window.ENDPOINT;
		// Could nullify any other script leaks here
	} catch (e) {
		console.warn("[PostProcess] Failed to clean some globals:", e);
	}

	// Revert or sanitize again (if needed)
	// Example: Disable console logs
	console.log = () => {};
	console.error = () => {};

	await new Promise((resolve) => setTimeout(resolve, 50));
	console.log("[PostProcess] Done.");
}
