// content-extractor.js
// This script is injected by the background service worker to extract page content.

(function () {
    console.log('VibeWorker Content Extractor injected.');

    // Helper to extract visible textual content
    function extractContent() {
        try {
            // Check if TurndownService is available (injected before this script)
            if (typeof TurndownService === 'undefined') {
                return { error: 'TurndownService is not loaded in the page.' };
            }

            // Clone body to manipulate without affecting user's view
            const clone = document.body.cloneNode(true);

            // Remove only disruptive elements, be careful not to remove content containers
            const elementsToRemove = clone.querySelectorAll('script, style, noscript, svg, .ad, .ads, .advertisement');
            elementsToRemove.forEach(el => el.remove());

            // Initialize Turndown
            const turndownService = new TurndownService({
                headingStyle: 'atx',
                codeBlockStyle: 'fenced'
            });

            // Convert HTML to Markdown
            let markdown = turndownService.turndown(clone.innerHTML);

            // Clean up excessive newlines or spaces
            markdown = markdown.replace(/\n{3,}/g, '\n\n').trim();

            return {
                title: document.title,
                url: window.location.href,
                markdown: markdown
            };
        } catch (error) {
            console.error('VibeWorker Extraction Error:', error);
            return { error: error.toString() };
        }
    }

    // Return the result back to the executing context (the background script)
    return extractContent();
})();
