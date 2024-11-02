// static/js/main.js
const ws = new WebSocket(`ws://${window.location.host}/ws`);

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateUI(data);
};

function updateUI(data) {
    // Update downloads list
    const downloadsContainer = document.getElementById('activeDownloads');
    downloadsContainer.innerHTML = '';
    
    data.downloads.forEach(download => {
        const element = createDownloadElement(download);
        downloadsContainer.appendChild(element);
    });
}

function createDownloadElement(download) {
    const div = document.createElement('div');
    div.className = 'download-item';
    div.innerHTML = `
        <div class="flex justify-between items-center">
            <div>
                <h3 class="font-semibold">${download.url}</h3>
                <p class="text-sm text-gray-600">${download.status}</p>
            </div>
            <div class="text-right">
                <p>${download.progress}%</p>
            </div>
        </div>
        <div class="progress-bar mt-2">
            <div class="progress-bar-fill" style="width: ${download.progress}%"></div>
        </div>
    `;
    return div;
}
</head> <body> <div class="container"> <div class="header"> <h1 class="title">ByteSec Download Manager</h1> <div class="author-info"> <span>Developed by b0urn3</span> </div> </div>

function initializeAnimations() {
    const buttons = document.querySelectorAll('.btn-animated');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            let ripple = document.createElement('span');
            ripple.classList.add('ripple');
            this.appendChild(ripple);

            let x = e.clientX - e.target.offsetLeft;
            let y = e.clientY - e.target.offsetTop;

            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;

            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
}

// Call after DOM loads
document.addEventListener('DOMContentLoaded', initializeAnimations);
