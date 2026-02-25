// API Reference: https://www.wix.com/velo/reference/api-overview/introduction
// “Hello, World!” Example: https://learn-code.wix.com/en/article/hello-world

$w.onReady(function () {
    // Example AI-generated UI tweak: update a text element and change page background.
    // This should result in a noticeable change on the homepage.

    // change background color; attempt multiple approaches to override black
    try {
        $w('#page').style.backgroundColor = '#800080'; // purple
    } catch (e) {
        // element might not exist; ignore
    }
    // also set document body directly as a backup
    if (typeof document !== 'undefined' && document.body) {
        document.body.style.backgroundColor = '#800080';
    }

    // update a generic text element (common default id)
    if ($w('#text1')) {
        $w('#text1').text = '🚀 This homepage has been updated by AI code';
        $w('#text1').style.color = '#d00';
    }

    // you can inspect elements in the Wix editor to adjust IDs further
});
