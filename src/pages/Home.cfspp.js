// API Reference: https://www.wix.com/velo/reference/api-overview/introduction
// “Hello, World!” Example: https://learn-code.wix.com/en/article/hello-world

$w.onReady(function () {
    // Example AI-generated UI tweak: update a text element and change page background.
    // This should result in a noticeable change on the homepage.

    // change background color of the page if an element with id 'page' exists
    try {
        $w('#page').style.backgroundColor = '#fffbdb';
    } catch (e) {
        // element might not exist; ignore
    }

    // update a generic text element (common default id)
    if ($w('#text1')) {
        $w('#text1').text = '🚀 This homepage has been updated by AI code';
        $w('#text1').style.color = '#d00';
    }

    // you can inspect elements in the Wix editor to adjust IDs further
});
