// content-executor.js
// This script is injected to execute DOM actions like clicks and typing.

(function () {
    console.log('VibeWorker Executor injected.');

    function executeAction(request) {
        try {
            const { action, selector, text } = request;

            if (!selector) {
                return { success: false, error: 'Selector is required.' };
            }

            const el = document.querySelector(selector);
            if (!el) {
                return { success: false, error: `Element not found for selector: ${selector}` };
            }

            if (action === 'click') {
                el.click();
                return { success: true, message: `Clicked element: ${selector}` };
            }
            else if (action === 'type') {
                // Focus the element first
                el.focus();

                // Directly setting value doesn't always trigger React/Vue states.
                // We need to dispatch native events.

                // Set the value (for traditional forms)
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,
                    "value"
                )?.set;

                const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype,
                    "value"
                )?.set;

                if (el.tagName.toLowerCase() === 'textarea' && nativeTextAreaValueSetter) {
                    nativeTextAreaValueSetter.call(el, text);
                } else if (nativeInputValueSetter) {
                    nativeInputValueSetter.call(el, text);
                } else {
                    el.value = text;
                }

                // Dispatch Input Event (React listens to this)
                el.dispatchEvent(new Event('input', { bubbles: true }));
                // Dispatch Change Event (Some frameworks listen to this)
                el.dispatchEvent(new Event('change', { bubbles: true }));

                // Optional: Dispatch Keydown/up for completeness if highly restricted
                el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter', keyCode: 13 }));
                el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter', keyCode: 13 }));

                return { success: true, message: `Typed text into: ${selector}` };
            }
            else {
                return { success: false, error: `Unknown action: ${action}` };
            }
        } catch (error) {
            console.error('VibeWorker Execution Error:', error);
            return { success: false, error: error.toString() };
        }
    }

    // We expect the background script to pass the args via an executeScript payload 
    // or by setting a global variable right before execution.
    // For chrome.scripting.executeScript with arguments, the arguments are passed to the function directly.
    return { status: 'ready' };
})();
