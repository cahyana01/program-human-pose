const state = {
    movement: 'Sikap Siap',
    mode: 'webcam'
};

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    loadReferences(state.movement);
    startStatusPolling();

    // Drag & Drop
    const dropZone = document.getElementById('drop-zone');
    dropZone.addEventListener('click', () => document.getElementById('test-input').click());

    document.getElementById('test-input').addEventListener('change', (e) => handleImageUpload(e.target.files[0]));

    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.borderColor = '#3b82f6'; });
    dropZone.addEventListener('dragleave', (e) => { e.preventDefault(); dropZone.style.borderColor = 'rgba(255,255,255,0.2)'; });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'rgba(255,255,255,0.2)';
        if (e.dataTransfer.files.length) handleImageUpload(e.dataTransfer.files[0]);
    });
});

function setMovement(mov) {
    state.movement = mov;
    document.getElementById('current-mov-display').innerText = mov;

    // Update Image Test selector too
    document.getElementById('image-test-movement').value = mov;

    // UI Active State
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    if (mov === 'Sikap Siap') document.getElementById('btn-sikap').classList.add('active');
    else document.getElementById('btn-pukulan').classList.add('active');

    // Load References for this movement
    loadReferences(mov);

    fetch('/set_movement', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movement: mov })
    });
}

function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
    // Simple toggle logic based on index
    const buttons = document.querySelectorAll('.mode-btn');
    if (mode === 'webcam') {
        buttons[0].classList.add('active');
        document.getElementById('webcam-view').classList.remove('hidden');
        document.getElementById('image-view').classList.add('hidden');
        document.getElementById('ref-manager-area').classList.remove('hidden'); // Show refs in webcam mode
    } else {
        buttons[1].classList.add('active');
        document.getElementById('webcam-view').classList.add('hidden');
        document.getElementById('image-view').classList.remove('hidden');
        document.getElementById('ref-manager-area').classList.add('hidden'); // Hide refs in upload mode? Or keep? Let's keep for utility.
        document.getElementById('ref-manager-area').classList.remove('hidden');
    }
}

function loadReferences(movement) {
    fetch(`/get_references?movement=${encodeURIComponent(movement)}`)
        .then(res => res.json())
        .then(data => {
            const grid = document.getElementById('ref-grid');
            grid.innerHTML = '';
            document.getElementById('ref-total-count').innerText = data.length;

            data.forEach(ref => {
                const card = document.createElement('div');
                card.type = 'div';
                card.className = 'ref-card';
                // Use annotated image for thumbnail
                const imgPath = `/static/uploads/${ref.filepath_annotated}`;
                card.innerHTML = `
                <img src="${imgPath}" alt="Ref" onclick="openModal('${imgPath}', '${movement}')">
                <button class="ref-del-btn" onclick="deleteReference(${ref.id})"><i class="fa-solid fa-trash"></i></button>
            `;
                grid.appendChild(card);
            });
        });
}

function openModal(src, movement) {
    const modal = document.getElementById("image-modal");
    const singleImg = document.getElementById("modal-single-img");
    const compareArea = document.getElementById("modal-compare-area");
    const captionText = document.getElementById("modal-caption");

    modal.style.display = "block";
    singleImg.style.display = "block";
    compareArea.style.display = "none";

    singleImg.src = src;
    captionText.innerHTML = `Reference for ${movement}`;
}

function openHistoryModal(item) {
    const modal = document.getElementById("history-modal") || document.getElementById("image-modal");
    const singleImg = document.getElementById("modal-single-img");
    const compareArea = document.getElementById("modal-compare-area") || document.getElementById("history-modal")?.querySelector(".modal-compare-container");
    const captionText = document.getElementById("modal-caption") || document.getElementById("modal-history-info");

    // Normalize elements for both index and history templates
    const resImg = document.getElementById("modal-result-img");
    const refImg = document.getElementById("modal-ref-img");

    if (resImg && refImg && compareArea) {
        modal.style.display = "block";
        if (singleImg) singleImg.style.display = "none";
        compareArea.style.display = "flex";

        resImg.src = `/static/uploads/${item.image_path}`;
        refImg.src = item.ref_path ? (item.ref_path.startsWith('http') ? item.ref_path : `/static/uploads/${item.ref_path}`) : 'https://placehold.co/300x200?text=No+Match';

        const scorePercent = item.score ? (item.score * 100).toFixed(1) : "N/A";
        let analysis = "";
        if (item.score > 0.95) analysis = "Sangat Mirip! Posisi tubuh hampir identik dengan referensi.";
        else if (item.score > 0.85) analysis = "Kemiripan Baik. Beberapa bagian tubuh mungkin perlu sedikit penyesuaian.";
        else if (item.score > 0.70) analysis = "Kemiripan Rendah. Periksa kembali sudut tangan atau kaki Anda.";
        else analysis = "Tidak Cocok atau Belum ada analisis bidang.";

        captionText.innerHTML = `
            <div style="font-weight: 700; font-size: 1.4rem; color: var(--accent);">${scorePercent}% Match Score</div>
            <div style="font-weight: 600; font-size: 1.1rem; margin-top: 5px;">${item.movement_type} - ${item.result}</div>
            <div style="color: var(--text-muted); font-size: 0.9rem; margin-top: 5px;">${item.timestamp}</div>
            <div style="margin-top: 15px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">
                <i class="fa-solid fa-circle-info"></i> ${analysis}
            </div>
        `;
    } else {
        // Fallback to single image if comparison elements not found
        openModal(`/static/uploads/${item.image_path}`, item.movement_type);
    }
}

function closeModal() {
    const modal = document.getElementById("image-modal");
    const historyModal = document.getElementById("history-modal");
    if (modal) modal.style.display = "none";
    if (historyModal) historyModal.style.display = "none";
}

function closeHistoryModal() {
    closeModal();
}

function deleteReference(id) {
    if (!confirm("Are you sure you want to delete this reference?")) return;

    fetch('/delete_reference', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadReferences(state.movement);
            }
        });
}

function uploadReferences() {
    const input = document.getElementById('ref-input');
    const files = input.files;
    if (files.length === 0) return;

    const formData = new FormData();
    formData.append('movement', state.movement);
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    const statusObj = document.getElementById('upload-status');
    statusObj.innerText = "Uploading & Processing...";

    fetch('/upload_references', {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                statusObj.innerText = `Saved ${data.count} refs!`;
                statusObj.style.color = 'var(--success)';
                loadReferences(state.movement);
            } else {
                statusObj.innerText = "Error: " + (data.error || "Failed");
                statusObj.style.color = 'var(--danger)';
            }
        })
        .catch(err => {
            statusObj.innerText = "Upload failed.";
        });
}

function verifyInstant() {
    const btn = document.querySelector('.instant-btn');
    const icon = btn.querySelector('i');
    const OriginalText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzing...`;

    fetch('/verify_instant', {
        method: 'POST'
    })
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = OriginalText;

            // Switch to Image view to show result
            setMode('image');

            const preview = document.getElementById('result-preview-container');
            preview.classList.remove('hidden');
            document.getElementById('drop-zone').classList.add('hidden');

            const sideBySide = document.getElementById('side-by-side-area');
            sideBySide.innerHTML = `
                <img src="${data.image_url}" alt="Result">
                ${data.best_ref ? `<img src="${data.best_ref}" alt="Reference">` : '<div style="width: 50%; display: flex; align-items: center; justify-content: center; color: #666;">No Match Found</div>'}
            `;

            document.getElementById('static-result-text').innerText = data.match ? "INSTANT VERIFIED" : "INCORRECT";
            document.getElementById('static-result-text').style.color = data.match ? "var(--success)" : "var(--danger)";

            loadHistory();
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = OriginalText;
            alert("Verification failed.");
        });
}

let currentUploadFile = null;

function handleImageUpload(file) {
    if (!file) return;
    currentUploadFile = file;

    // Show preview only
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('drop-zone').classList.add('hidden');
        document.getElementById('result-preview-container').classList.add('hidden'); // Hide results if any
        document.getElementById('preview-area').classList.remove('hidden');
        document.getElementById('upload-preview-img').src = e.target.result;
    };
    reader.readAsDataURL(file);
}

function runStaticVerification() {
    if (!currentUploadFile) return;

    const btn = document.getElementById('verify-photo-btn');
    const OriginalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Verifying...`;

    const selectedMov = document.getElementById('image-test-movement').value;
    const formData = new FormData();
    formData.append('file', currentUploadFile);
    formData.append('movement', selectedMov);

    fetch('/verify_image', {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = OriginalText;

            document.getElementById('preview-area').classList.add('hidden');
            const resultContainer = document.getElementById('result-preview-container');
            resultContainer.classList.remove('hidden');

            const sideBySide = document.getElementById('side-by-side-area');
            const resultUrl = data.image_url;
            const refUrl = data.best_ref ? data.best_ref : 'https://placehold.co/300x200?text=No+Match';

            // Create item object for modal consistency
            const item = {
                image_path: resultUrl.split('/').pop(),
                ref_path: data.best_ref ? data.best_ref.split('/').pop() : null,
                movement_type: selectedMov,
                result: data.match ? "Correct" : "Incorrect",
                timestamp: new Date().toLocaleString(),
                score: data.score
            };

            sideBySide.onclick = () => openHistoryModal(item);
            sideBySide.style.cursor = 'pointer';

            sideBySide.innerHTML = `
                <img src="${resultUrl}" alt="Result">
                ${data.best_ref ? `<img src="${data.best_ref}" alt="Reference">` : '<div style="width: 50%; display: flex; align-items: center; justify-content: center; color: #666;">No Match Found</div>'}
            `;

            const statusLabel = document.getElementById('static-result-text');
            statusLabel.innerText = data.match ? "VERIFIED (Correct)" : "INCORRECT POSE";
            statusLabel.style.color = data.match ? "var(--success)" : "var(--danger)";

            loadHistory();
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = OriginalText;
            alert("Verification failed.");
        });
}

function resetImageTest() {
    document.getElementById('result-preview-container').classList.add('hidden');
    document.getElementById('preview-area').classList.add('hidden');
    document.getElementById('drop-zone').classList.remove('hidden');
    document.getElementById('test-input').value = '';
    currentUploadFile = null;
}

function loadHistory() {
    fetch('/history')
        .then(res => res.json())
        .then(data => {
            const list = document.getElementById('history-list');
            list.innerHTML = '';
            data.forEach(item => {
                const div = document.createElement('div');
                div.className = `history-item ${item.result}`;
                div.innerHTML = `
                <div class="history-content">
                    <div class="history-time">${item.timestamp}</div>
                    <div class="history-res">${item.movement_type} - ${item.result}</div>
                </div>
                <i class="fa-solid fa-trash icon-trash" onclick="deleteHistoryItem(${item.id})"></i>
            `;
                list.appendChild(div);
            });
        });
}

function deleteHistoryItem(id) {
    fetch('/delete_history_item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id })
    }).then(loadHistory);
}

function clearHistory() {
    if (!confirm("Clear all history?")) return;
    fetch('/clear_history', { method: 'POST' }).then(loadHistory);
}

function startStatusPolling() {
    setInterval(() => {
        // Only poll if in webcam mode
        if (state.mode !== 'webcam') return;

        fetch('/status')
            .then(res => res.json())
            .then(data => {
                // Update Polling UI
                document.getElementById('verify-progress').style.width = data.progress + '%';
                document.getElementById('live-status').innerText = data.status;

                // Update detection info
                document.getElementById('detected-mov-badge').innerText = data.detected;
                document.getElementById('score-sikap').innerText = data.scores['Sikap Siap'].toFixed(2);
                document.getElementById('score-pukulan').innerText = data.scores['Pukulan Dasar'].toFixed(2);

                // Update ref counts
                document.getElementById('ref-count-sikap').innerText = `${data.ref_counts['Sikap Siap']} Refs`;
                document.getElementById('ref-count-pukulan').innerText = `${data.ref_counts['Pukulan Dasar']} Refs`;

                if (data.verified) {
                    document.getElementById('live-status').style.color = 'var(--success)';
                    loadHistory(); // Reload if verified
                } else {
                    document.getElementById('live-status').style.color = 'white';
                }
            });
    }, 500);
}
