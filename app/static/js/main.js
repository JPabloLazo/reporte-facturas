document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    initDragDrop();
    initDrive();
    initPreview();
    initResults();
    initConfig();
    initCardModal();
    initAddCardModal();
    initToast();
    loadConfig();
});

/* ============== Tabs ============== */
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var tabId = this.getAttribute('data-tab');
            document.querySelectorAll('.tab-content').forEach(function (el) {
                el.classList.add('hidden');
            });
            document.querySelectorAll('.tab-btn').forEach(function (b) {
                b.classList.remove('border-blue-600', 'text-blue-600');
                b.classList.add('text-gray-500');
            });
            var target = document.getElementById('tab-' + tabId);
            if (target) target.classList.remove('hidden');
            this.classList.remove('text-gray-500');
            this.classList.add('border-blue-600', 'text-blue-600');
        });
    });
}

/* ============== Toast ============== */
var toastTimeout;

function initToast() {}

function showToast(message, type) {
    type = type || 'success';
    var container = document.getElementById('toast-container');
    if (!container) return;
    var colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        info: 'bg-blue-600',
        warning: 'bg-yellow-500 text-gray-800'
    };
    var bg = colors[type] || colors.info;
    var toast = document.createElement('div');
    toast.className = 'toast ' + bg + ' text-white px-4 py-3 rounded-lg shadow-lg text-sm max-w-sm';
    toast.textContent = message;
    container.appendChild(toast);
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(function () {
        toast.classList.add('toast-leave');
        setTimeout(function () { toast.remove(); }, 300);
    }, 4000);
}

/* ============== Drag & Drop ============== */
function initDragDrop() {
    var zone = document.getElementById('drop-zone');
    var input = document.getElementById('file-input');
    var fileInfo = document.getElementById('file-info');
    var fileName = document.getElementById('file-name');
    var fileType = document.getElementById('file-type');
    var progress = document.getElementById('upload-progress');

    if (!zone) return;

    zone.addEventListener('click', function () { input.click(); });

    input.addEventListener('change', function () {
        if (this.files.length) handleFile(this.files[0]);
    });

    zone.addEventListener('dragover', function (e) {
        e.preventDefault();
        this.classList.add('drop-zone-dragover');
    });

    zone.addEventListener('dragleave', function () {
        this.classList.remove('drop-zone-dragover');
    });

    zone.addEventListener('drop', function (e) {
        e.preventDefault();
        this.classList.remove('drop-zone-dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });

    function handleFile(file) {
        if (file.type !== 'application/pdf') {
            showToast('Solo se aceptan archivos PDF', 'error');
            return;
        }
        fileName.textContent = file.name;
        fileType.textContent = 'Analizando...';
        fileInfo.classList.remove('hidden');
        uploadFile(file);
    }

    function uploadFile(file) {
        progress.classList.remove('hidden');
        var formData = new FormData();
        formData.append('file', file);

        fetch('/api/upload', { method: 'POST', body: formData })
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (errData) {
                        throw new Error(errData.detail || errData.message || 'Error al subir archivo');
                    }).catch(function (parseErr) {
                        if (parseErr instanceof Error) throw parseErr;
                        throw new Error('Error al subir archivo');
                    });
                }
                return res.json();
            })
            .then(function (data) {
                progress.classList.add('hidden');
                window._resumenId = data.id;
                window._uploadPeriodo = data.periodo;

                // Always update file-info after upload
                var ds = document.getElementById('drive-section');
                if (ds) ds.classList.remove('hidden');

                if (data.transacciones && data.transacciones.length > 0) {
                    document.getElementById('file-info').innerHTML =
                        '<span class="text-green-600 font-medium">' + escapeHtml(data.archivo || '') + '</span>' +
                        ' — <span class="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">' + escapeHtml(data.tipo || '') + '</span>' +
                        ' — <span class="text-xs text-gray-500">' + data.transacciones.length + ' transacciones</span>';

                    showTransactionsTable(data);
                    showToast('Archivo procesado correctamente', 'success');
                } else {
                    document.getElementById('file-info').innerHTML =
                        '<span class="text-amber-600 font-medium">' + escapeHtml(data.archivo || '') + '</span>' +
                        ' — <span class="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">' + (data.tipo || 'Sin tipo') + '</span>' +
                        ' — <span class="text-xs text-gray-400">sin transacciones</span>';
                    showToast('Archivo subido pero no se detectaron transacciones', 'warning');
                }

                if (data.warnings && data.warnings.length > 0) {
                    data.warnings.forEach(function (w) {
                        if (w.codigo === 'TARJETAS_SIN_MAPEO') {
                            showToast('Tarjetas nuevas detectadas: ' + (w.tarjetas || []).join(', ') + ' — asignales un responsable en la tabla', 'warning');
                        }
                    });
                }
            })
            .catch(function (err) {
                progress.classList.add('hidden');
                document.getElementById('file-info').classList.add('hidden');
                document.getElementById('file-input').value = '';
                document.getElementById('file-info').innerHTML = '';
                showToast(err.message, 'error');
            });
    }
}

/* ============== Drive ============== */
function initDrive() {
    // Check for OAuth callback result in URL
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('drive') === 'connected') {
        // Clean URL without reload
        if (window.history.replaceState) {
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        checkDriveStatus();
    } else if (urlParams.get('drive') === 'error') {
        if (window.history.replaceState) {
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        showToast('Error al conectar Drive: ' + (urlParams.get('message') || 'desconocido'), 'error');
    }

    checkDriveStatus();

    var connectBtn = document.getElementById('btn-connect-drive');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectDrive);
    }

    var disconnectBtn = document.getElementById('btn-disconnect-drive');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectDrive);
    }

    // Locked connect button
    var lockedBtn = document.getElementById('btn-connect-drive-locked');
    if (lockedBtn) {
        lockedBtn.addEventListener('click', connectDrive);
    }

    // Breadcrumb root click
    var breadcrumbRoot = document.getElementById('breadcrumb-root');
    if (breadcrumbRoot) {
        breadcrumbRoot.addEventListener('click', function () {
            _folderStack = [{id: 'root', name: 'Drive'}];
            updateBreadcrumb();
            browseDrive('root');
        });
    }

    // Select current folder button
    var selectBtn = document.getElementById('btn-select-current-folder');
    if (selectBtn) {
        selectBtn.addEventListener('click', function () {
            var currentFolderId = _folderStack[_folderStack.length - 1].id;
            var currentFolderName = _folderStack[_folderStack.length - 1].name;
            selectFolderForProcessing(currentFolderId, currentFolderName);
        });
    }

    // Back to browse button
    var backBtn = document.getElementById('btn-back-to-browse');
    if (backBtn) {
        backBtn.addEventListener('click', function () {
            var filesContainer = document.getElementById('files-container');
            var nav = document.getElementById('drive-navigation');
            if (filesContainer) filesContainer.classList.add('hidden');
            if (nav) nav.classList.remove('hidden');
            browseDrive(_folderStack[_folderStack.length - 1].id);
        });
    }

    window.addEventListener('message', function (event) {
        if (event.data && event.data.type === 'drive-connected') {
            showToast('Google Drive conectado como ' + (event.data.email || ''), 'success');
            checkDriveStatus();
        }
        if (event.data && event.data.type === 'drive-error') {
            showToast('Error al conectar Drive: ' + (event.data.message || ''), 'error');
        }
    });
}

function checkDriveStatus() {
    fetch('/api/drive/auth/check')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            var locked = document.getElementById('drive-locked');
            var content = document.getElementById('drive-connected-content');
            var connectPanel = document.getElementById('drive-connect-panel');
            var browserPanel = document.getElementById('drive-browser-panel');
            var userEmail = document.getElementById('drive-user-email');
            var userInfo = document.getElementById('drive-user-info');

            if (data.connected) {
                if (locked) locked.classList.add('hidden');
                if (content) content.classList.remove('hidden');
                if (connectPanel) connectPanel.classList.add('hidden');
                if (browserPanel) browserPanel.classList.remove('hidden');

                if (userEmail && data.email) {
                    userEmail.textContent = data.email;
                    if (userInfo) userInfo.classList.remove('hidden');
                }

                // Restore last path from localStorage
                _folderStack = [{id: 'root', name: 'Drive'}];
                try {
                    var savedPath = localStorage.getItem('drive-last-path');
                    if (savedPath) {
                        var parsed = JSON.parse(savedPath);
                        if (Array.isArray(parsed) && parsed.length > 0) {
                            _folderStack = parsed;
                        }
                    }
                } catch(e) {}

                updateBreadcrumb();
                browseDrive(_folderStack[_folderStack.length - 1].id);
            } else {
                if (locked) locked.classList.remove('hidden');
                if (content) content.classList.add('hidden');
                if (connectPanel) connectPanel.classList.remove('hidden');
                if (browserPanel) browserPanel.classList.add('hidden');
                if (userInfo) userInfo.classList.add('hidden');
                _folderStack = [{id: 'root', name: 'Drive'}];
            }
        })
        .catch(function () {});
}

function connectDrive() {
    fetch('/api/drive/auth/google')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.needs_config) {
                showToast(data.message || 'Configurá Google Drive en la pestaña Configuración', 'warning');
                var configTab = document.querySelector('[data-tab="config"]');
                if (configTab) configTab.click();
                return;
            }
            if (data.auth_url) {
                // Redirect the main window to Google OAuth
                window.location.href = data.auth_url;
            } else {
                showToast(data.error || 'Error al obtener URL de auth', 'error');
            }
        })
        .catch(function (err) {
            showToast('Error al conectar Drive: ' + err.message, 'error');
        });
}
function disconnectDrive() {
    fetch('/api/drive/auth/disconnect', { method: 'POST' })
        .then(function (res) { return res.json(); })
        .then(function () {
            showToast('Drive desconectado', 'info');
            checkDriveStatus();
            clearDriveUI();
        })
        .catch(function (err) {
            showToast('Error al desconectar: ' + err.message, 'error');
        });
}

function clearDriveUI() {
    _folderStack = [{id: 'root', name: 'Drive'}];
    ['folders-container', 'files-preview-container', 'files-container', 'facturas-info'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    var processBtn = document.getElementById('btn-list-facturas');
    if (processBtn) { processBtn.classList.add('hidden'); processBtn.disabled = true; }
    var nav = document.getElementById('drive-navigation');
    if (nav) nav.classList.remove('hidden');
    document.getElementById('folders-list').innerHTML = '';
    document.getElementById('files-preview-list').innerHTML = '';
    document.getElementById('files-list').innerHTML = '';
    updateBreadcrumb();
}

/* ============== Drive Folder Browser ============== */
var _folderStack = [{id: 'root', name: 'Drive'}];

function loadFolder(folderId, folderName) {
    if (folderId !== _folderStack[_folderStack.length-1].id) {
        _folderStack.push({id: folderId, name: folderName});
    }
    updateBreadcrumb();
    browseDrive(folderId);
}

function goToFolder(index) {
    if (index < 0) index = 0;
    _folderStack = _folderStack.slice(0, index + 1);
    updateBreadcrumb();
    browseDrive(_folderStack[index].id);
}

function updateBreadcrumb() {
    var container = document.getElementById('breadcrumb-path');
    container.innerHTML = '';
    var parts = '';
    _folderStack.forEach(function(f, i) {
        if (i === 0) return;
        parts += ' / ';
        var span = document.createElement('span');
        if (i === _folderStack.length - 1) {
            span.className = 'text-gray-800 font-medium';
            span.textContent = f.name;
        } else {
            span.className = 'text-blue-600 cursor-pointer hover:underline';
            span.textContent = f.name;
            span.onclick = function() { goToFolder(i); };
        }
        container.appendChild(document.createTextNode(parts));
        container.appendChild(span);
    });
}

function browseDrive(parentId) {
    var foldersContainer = document.getElementById('folders-container');
    var filesPreview = document.getElementById('files-preview-container');
    var selectBtn = document.getElementById('btn-select-current-folder');
    var loading = document.getElementById('browse-loading');
    var foldersList = document.getElementById('folders-list');
    var filesList = document.getElementById('files-preview-list');
    var processBtn = document.getElementById('btn-list-facturas');

    if (foldersContainer) foldersContainer.classList.add('hidden');
    if (filesPreview) filesPreview.classList.add('hidden');
    if (selectBtn) selectBtn.classList.add('hidden');
    if (loading) loading.classList.remove('hidden');
    if (processBtn) processBtn.classList.add('hidden');

    fetch('/api/drive/browse?parent_id=' + encodeURIComponent(parentId))
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (loading) loading.classList.add('hidden');

            var pathStr = JSON.stringify(_folderStack);
            try { localStorage.setItem('drive-last-path', pathStr); } catch(e) {}

            if (data.folders && data.folders.length > 0) {
                foldersList.innerHTML = '';
                data.folders.forEach(function (f) {
                    var card = document.createElement('div');
                    card.className = 'border rounded-lg p-3 bg-white hover:bg-blue-50 cursor-pointer transition-colors flex items-center gap-2';
                    card.innerHTML = '<span class="text-xl">📁</span><div class="min-w-0 flex-1"><p class="text-sm font-medium text-gray-800 truncate">' + escapeHtml(f.name) + '</p><p class="text-xs text-gray-400">carpeta</p></div>';
                    card.addEventListener('click', function () {
                        loadFolder(f.id, f.name);
                    });
                    foldersList.appendChild(card);
                });
                foldersContainer.classList.remove('hidden');
            } else {
                foldersList.innerHTML = '<p class="text-sm text-gray-400 col-span-full py-4 text-center">No hay subcarpetas aquí.</p>';
                foldersContainer.classList.remove('hidden');
            }

            if (data.files && data.files.length > 0) {
                filesList.innerHTML = '';
                data.files.forEach(function (f) {
                    var row = document.createElement('div');
                    row.className = 'flex items-center gap-2 text-sm';
                    var icon = getFileIcon(f.mimeType);
                    var size = f.size ? ' (' + formatFileSize(parseInt(f.size)) + ')' : '';
                    var date = f.modifiedTime ? new Date(f.modifiedTime).toLocaleDateString('es-AR') : '';
                    row.innerHTML = '<span>' + icon + '</span><span class="text-gray-700 truncate flex-1">' + escapeHtml(f.name) + '</span><span class="text-xs text-gray-400">' + size + '</span><span class="text-xs text-gray-400">' + date + '</span>';
                    filesList.appendChild(row);
                });
                filesPreview.classList.remove('hidden');
            } else {
                filesPreview.classList.remove('hidden');
                filesList.innerHTML = '<p class="text-sm text-gray-400">No hay archivos en esta carpeta.</p>';
            }

            if (selectBtn) selectBtn.classList.remove('hidden');
        })
        .catch(function (err) {
            if (loading) loading.classList.add('hidden');
            showToast('Error al navegar: ' + err.message, 'error');
        });
}

function getFileIcon(mimeType) {
    if (mimeType === 'application/pdf') return '📄';
    if (mimeType.startsWith('image/')) return '🖼️';
    if (mimeType.startsWith('video/')) return '🎬';
    if (mimeType.startsWith('text/') || mimeType.includes('xml') || mimeType.includes('json')) return '📝';
    if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) return '📊';
    if (mimeType.includes('document') || mimeType.includes('word')) return '📃';
    return '📎';
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatFileSize(bytes) {
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return bytes + ' B';
}

function selectFolderForProcessing(folderId, folderName) {
    window._selectedFolderId = folderId;
    window._selectedFolderName = folderName;

    try { localStorage.setItem('drive-last-selected-folder', JSON.stringify({id: folderId, name: folderName, path: _folderStack})); } catch(e) {}

    fetch('/api/drive/files?folder_id=' + encodeURIComponent(folderId))
        .then(function (res) { return res.json(); })
        .then(function (data) {
            var filesContainer = document.getElementById('files-container');
            var filesList = document.getElementById('files-list');
            var facturasInfo = document.getElementById('facturas-info');
            var processBtn = document.getElementById('btn-list-facturas');
            var facturasCount = document.getElementById('facturas-count');
            var selectBtn = document.getElementById('btn-select-current-folder');

            var nav = document.getElementById('drive-navigation');
            if (nav) nav.classList.add('hidden');
            if (selectBtn) selectBtn.classList.add('hidden');

            if (filesContainer) filesContainer.classList.remove('hidden');
            if (filesList) {
                filesList.innerHTML = '';
                (data.files || []).forEach(function (f) {
                    var row = document.createElement('label');
                    row.className = 'flex items-center gap-3 p-2 bg-white rounded border hover:bg-gray-50 cursor-pointer';
                    var icon = getFileIcon(f.mimeType);
                    var size = f.size ? ' (' + formatFileSize(parseInt(f.size)) + ')' : '';
                    row.innerHTML =
                        '<input type="checkbox" class="file-checkbox w-4 h-4 text-blue-600" value="' + f.id + '" checked>' +
                        '<span class="text-lg">' + icon + '</span>' +
                        '<div class="flex-1 min-w-0">' +
                        '<p class="text-sm font-medium text-gray-800 truncate">' + escapeHtml(f.name) + '</p>' +
                        '<p class="text-xs text-gray-400">' + (f.mimeType || '') + size + '</p>' +
                        '</div>';
                    filesList.appendChild(row);

                    row.querySelector('.file-checkbox').addEventListener('change', updateProcessButton);
                });
            }

            if (facturasInfo) {
                facturasInfo.classList.remove('hidden');
                if (facturasCount) facturasCount.textContent = data.files ? data.files.length : 0;
            }

            var processBtn = document.getElementById('btn-list-facturas');
            if (processBtn) {
                processBtn.classList.remove('hidden');
                processBtn.disabled = false;
                updateProcessButton();
            }
        })
        .catch(function (err) {
            showToast('Error al listar archivos: ' + err.message, 'error');
        });
}

function updateProcessButton() {
    var selected = document.querySelectorAll('.file-checkbox:checked').length;
    var countEl = document.getElementById('facturas-count');
    var infoEl = document.getElementById('facturas-info');
    var processBtn = document.getElementById('btn-list-facturas');
    var notice = document.getElementById('resumen-notice');

    if (countEl) countEl.textContent = selected;
    if (infoEl) infoEl.classList.remove('hidden');
    if (processBtn) {
        if (selected > 0 && window._resumenId && window._selectedFolderId) {
            processBtn.disabled = false;
            if (notice) notice.classList.add('hidden');
        } else {
            processBtn.disabled = true;
            // Show why button is disabled
            if (notice) {
                if (!window._resumenId) {
                    notice.innerHTML = '⚠️ Primero subí un resumen PDF en la sección de arriba';
                } else if (!window._selectedFolderId) {
                    notice.innerHTML = '⚠️ Seleccioná una carpeta de Drive primero';
                } else {
                    notice.innerHTML = '⚠️ Seleccioná al menos un archivo';
                }
                notice.classList.remove('hidden');
            }
        }
    }
}

function setAllFiles(checked) {
    document.querySelectorAll('.file-checkbox').forEach(function (cb) { cb.checked = checked; });
    updateProcessButton();
}

function getSelectedFileIds() {
    var ids = [];
    document.querySelectorAll('.file-checkbox:checked').forEach(function (cb) { ids.push(cb.value); });
    return ids;
}

/* ============== Results ============== */
function initResults() {
    // Process reconciliation button
    var processBtn = document.getElementById('btn-list-facturas');
    if (processBtn) {
        // Start disabled, handler manages state
        processBtn.disabled = true;
        processBtn.addEventListener('click', function() {
            var resumenId = window._resumenId;
            var folderId = window._selectedFolderId;
            if (!resumenId || !folderId) {
                showToast('Falta resumen o carpeta de Drive seleccionada', 'error');
                return;
            }

            var spinner = document.getElementById('processing-spinner');
            if (spinner) spinner.classList.remove('hidden');
            processBtn.disabled = true;

            var selectedIds = getSelectedFileIds();
            var url = '/api/process/process?resumen_id=' + resumenId + '&carpeta_drive_id=' + encodeURIComponent(folderId);

            fetch(url, { method: 'POST' })
                .then(function(res) {
                    if (!res.ok) {
                        return res.json().then(function(err) {
                            throw new Error(err.detail || 'Error en conciliación');
                        });
                    }
                    return res.json();
                })
                .then(function(data) {
                    if (spinner) spinner.classList.add('hidden');
                    processBtn.disabled = false;
                    showResults(data);
                })
                .catch(function(err) {
                    if (spinner) spinner.classList.add('hidden');
                    processBtn.disabled = false;
                    showToast('Error: ' + err.message, 'error');
                });
        });
    }

    // Download Excel dropdown
    var downloadBtn = document.getElementById('btn-download-excel');
    if (downloadBtn) {
        downloadBtn.classList.add('relative');
        downloadBtn.innerHTML = 'Descargar Excel';

        var dropdown = document.createElement('div');
        dropdown.className = 'absolute top-full left-0 mt-1 bg-white border rounded-lg shadow-lg z-10 hidden';
        dropdown.innerHTML =
            '<button class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 download-option" data-filter="unmatched">Solo sin factura</button>' +
            '<button class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 download-option" data-filter="matched">Solo con factura</button>' +
            '<button class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 download-option" data-filter="all">Todos</button>';
        downloadBtn.appendChild(dropdown);

        downloadBtn.addEventListener('click', function(e) {
            if (e.target === downloadBtn || e.target.tagName === 'SPAN') {
                dropdown.classList.toggle('hidden');
            }
        });

        dropdown.querySelectorAll('.download-option').forEach(function(opt) {
            opt.addEventListener('click', function() {
                var filter = this.getAttribute('data-filter');
                dropdown.classList.add('hidden');
                if (window._resumenId) {
                    window.location.href = '/api/reports/' + window._resumenId + '/excel?filter=' + filter;
                }
            });
        });

        document.addEventListener('click', function(e) {
            if (!downloadBtn.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });
    }

    var sendBtn = document.getElementById('btn-send-emails');

    if (sendBtn) {
        sendBtn.addEventListener('click', function () {
            sendBtn.disabled = true;
            sendBtn.textContent = 'Enviando...';
            fetch('/api/reports/' + (window._resumenId || '') + '/email', { method: 'POST' })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    showToast('Emails enviados correctamente', 'success');
                })
                .catch(function (err) {
                    showToast('Error al enviar emails: ' + err.message, 'error');
                })
                .finally(function () {
                    sendBtn.disabled = false;
                    sendBtn.textContent = 'Enviar Emails';
                });
        });
    }
}

function showTransactionsTable(data) {
    var section = document.getElementById('transactions-section');
    if (!section) return;
    section.classList.remove('hidden');

    document.getElementById('tx-summary-tipo').textContent = data.tipo || '-';
    document.getElementById('tx-summary-count').textContent = (data.transacciones || []).length;
    document.getElementById('tx-summary-periodo').textContent = data.periodo || '-';

    var tbody = document.getElementById('transactions-tbody');
    tbody.innerHTML = '';
    (data.transacciones || []).forEach(function (t) {
        var cuotaStr = '';
        if (t.cantidad_cuotas && t.cantidad_cuotas > 1) {
            cuotaStr = t.cuota_numero + '/' + t.cantidad_cuotas;
        } else {
            cuotaStr = '-';
        }
        var montoStr = '$' + Number(t.monto).toLocaleString('es-AR', {minimumFractionDigits: 2});
        var row = document.createElement('tr');
        row.className = 'border-b hover:bg-gray-50';
        row.innerHTML =
            '<td class="py-2 px-4 text-sm">' + (t.fecha || '') + '</td>' +
            '<td class="py-2 px-4 text-sm">' + (t.descripcion || '') + '</td>' +
            '<td class="py-2 px-4 text-sm text-right font-medium">' + montoStr + '</td>' +
            '<td class="py-2 px-4 text-sm text-center">' + (t.moneda || 'ARS') + '</td>' +
            '<td class="py-2 px-4 text-sm text-center">' + cuotaStr + '</td>';
        tbody.appendChild(row);
    });

    // Wire download buttons
    var rid = window._resumenId;
    document.getElementById('btn-download-tx-excel').onclick = function () {
        window.location.href = '/api/reports/' + rid + '/transactions/excel';
    };
    document.getElementById('btn-download-tx-pdf').onclick = function () {
        window.location.href = '/api/reports/' + rid + '/transactions/pdf';
    };
}

function showResults(data) {
    var section = document.getElementById('results-section');
    if (!section) return;
    section.classList.remove('hidden');

    var matched = data.resumen ? data.resumen.matched : 0;
    var unmatched = data.resumen ? data.resumen.unmatched : 0;
    var total = data.resumen ? data.resumen.total : 0;

    document.getElementById('match-count').textContent = matched;
    document.getElementById('unmatch-count').textContent = unmatched;
    document.getElementById('result-periodo').textContent = data.periodo || 'Procesado';

    var tbody = document.getElementById('results-tbody');
    tbody.innerHTML = '';

    var rows = data.resultados || [];
    rows.forEach(function(r) {
        var tr = document.createElement('tr');
        tr.className = 'border-b hover:bg-gray-50';
        tr.setAttribute('data-estado', r.estado);

        var statusClass = r.estado === 'MATCHED' ? 'text-green-600' : 'text-red-600';
        var statusBadge = r.estado === 'MATCHED'
            ? '<span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-medium">Match</span>'
            : '<span class="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-medium">Sin factura</span>';
        var confianzaText = r.confianza ? (r.confianza * 100).toFixed(0) + '%' : '—';
        var montoStr = r.monto != null ? '$ ' + Number(r.monto).toLocaleString('es-AR') : '—';

        tr.innerHTML =
            '<td class="py-3 px-4 text-gray-600">' + (r.fecha || '—') + '</td>' +
            '<td class="py-3 px-4 text-gray-800">' + escapeHtml(r.descripcion || '—') + '</td>' +
            '<td class="py-3 px-4 text-right text-gray-800">' + montoStr + '</td>' +
            '<td class="py-3 px-4 text-center ' + statusClass + '">' + statusBadge + '</td>' +
            '<td class="py-3 px-4 text-center text-xs text-gray-500">' + confianzaText + '</td>' +
            '<td class="py-3 px-4 text-center text-xs text-gray-500">' + (r.metodo || '—') + '</td>';
        tbody.appendChild(tr);
    });

    window._resumenId = data.resumen_id;

    var filterContainer = document.getElementById('results-filter');
    if (!filterContainer) {
        filterContainer = document.createElement('div');
        filterContainer.id = 'results-filter';
        filterContainer.className = 'flex gap-2 mb-3';
        filterContainer.innerHTML =
            '<button class="filter-btn text-xs px-3 py-1 rounded-full bg-blue-600 text-white" data-filter="all">Todos</button>' +
            '<button class="filter-btn text-xs px-3 py-1 rounded-full bg-gray-200 text-gray-600 hover:bg-gray-300" data-filter="MATCHED">Con factura</button>' +
            '<button class="filter-btn text-xs px-3 py-1 rounded-full bg-gray-200 text-gray-600 hover:bg-gray-300" data-filter="UNMATCHED">Sin factura</button>';
        var table = tbody.closest('.overflow-x-auto');
        if (table) table.parentNode.insertBefore(filterContainer, table);

        filterContainer.querySelectorAll('.filter-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var filter = this.getAttribute('data-filter');
                filterContainer.querySelectorAll('.filter-btn').forEach(function(b) {
                    b.className = 'filter-btn text-xs px-3 py-1 rounded-full bg-gray-200 text-gray-600 hover:bg-gray-300';
                });
                this.className = 'filter-btn text-xs px-3 py-1 rounded-full bg-blue-600 text-white';

                tbody.querySelectorAll('tr').forEach(function(row) {
                    if (filter === 'all') {
                        row.style.display = '';
                    } else {
                        var estado = row.getAttribute('data-estado');
                        row.style.display = estado === filter ? '' : 'none';
                    }
                });
            });
        });
    }

    showToast('Conciliación completada: ' + matched + ' match, ' + unmatched + ' sin factura', 'success');
}

/* ============== Config ============== */
function initConfig() {
    var saveBtn = document.getElementById('btn-save-config');
    if (!saveBtn) return;

    saveBtn.addEventListener('click', function () {
        var config = {
            llm_provider: getVal('cfg-llm-provider'),
            anthropic_key: getVal('cfg-anthropic-key'),
            openai_key: getVal('cfg-openai-key'),
            openrouter_key: getVal('cfg-openrouter-key'),
            model_extract: getVal('cfg-model-extract'),
            model_fallback: getVal('cfg-model-fallback'),
            model_cheap: getVal('cfg-model-cheap'),
            model_email: getVal('cfg-model-email'),
            smtp_host: getVal('cfg-smtp-host'),
            smtp_port: parseInt(getVal('cfg-smtp-port')) || 587,
            smtp_user: getVal('cfg-smtp-user'),
            smtp_pass: getVal('cfg-smtp-pass'),
            responsable_email: getVal('cfg-responsable-email')
        };

        saveBtn.disabled = true;
        saveBtn.textContent = 'Guardando...';

        fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        })
            .then(function (res) {
                if (!res.ok) throw new Error('Error al guardar');
                return res.json();
            })
            .then(function () {
                showToast('Configuración guardada correctamente', 'success');
            })
            .catch(function (err) {
                showToast(err.message, 'error');
            })
            .finally(function () {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Guardar configuración';
            });
    });

    function getVal(id) {
        var el = document.getElementById(id);
        return el ? el.value : '';
    }
}

function loadConfig() {
    fetch('/api/config')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            setVal('cfg-llm-provider', data.llm_provider);
            setVal('cfg-anthropic-key', data.anthropic_key || '');
            setVal('cfg-openai-key', data.openai_key || '');
            setVal('cfg-model-extract', data.model_extract);
            setVal('cfg-model-fallback', data.model_fallback);
            setVal('cfg-model-cheap', data.model_cheap);
            setVal('cfg-model-email', data.model_email);
            setVal('cfg-smtp-host', data.smtp_host || 'smtp.gmail.com');
            setVal('cfg-smtp-port', data.smtp_port || 587);
            setVal('cfg-smtp-user', data.smtp_user || '');
            setVal('cfg-smtp-pass', data.smtp_pass || '');
            setVal('cfg-responsable-email', data.responsable_email || '');

            if (data.cards) {
                renderCards(data.cards);
            }

            // Load available models
            loadAvailableModels();
        })
        .catch(function () {});
}

function setVal(id, val) {
    var el = document.getElementById(id);
    if (el) el.value = val != null ? val : '';
}

function renderCards(cards) {
    var tbody = document.getElementById('cards-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (cards || []).forEach(function (c) {
        var tr = document.createElement('tr');
        tr.className = 'border-b';
        tr.innerHTML =
            '<td class="py-2 px-3 text-gray-600">' + (c.card_suffix || '') + '</td>' +
            '<td class="py-2 px-3 text-gray-800">' + (c.responsable || '') + '</td>' +
            '<td class="py-2 px-3 text-gray-600">' + (c.email || '') + '</td>' +
            '<td class="py-2 px-3 text-center">' +
            '<button class="text-red-600 text-xs hover:text-red-700" data-card-id="' + (c.id || '') + '">Eliminar</button>' +
            '</td>';
        tbody.appendChild(tr);
    });

    tbody.querySelectorAll('[data-card-id]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-card-id');
            if (!id) return;
            fetch('/api/config/cards/' + id, { method: 'DELETE' })
                .then(function () {
                    this.closest('tr').remove();
                    showToast('Tarjeta eliminada', 'info');
                }.bind(this))
                .catch(function (err) {
                    showToast('Error al eliminar: ' + err.message, 'error');
                });
        });
    });
}

/* ============== Dynamic Model List ============== */
function loadAvailableModels() {
    fetch('/api/config/models')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var models = data.models || [];
            populateModelSelect('cfg-model-extract', models);
            populateModelSelect('cfg-model-fallback', models);
            populateModelSelect('cfg-model-cheap', models);
            populateModelSelect('cfg-model-email', models);

            // Restore saved values after populating
            fetch('/api/config')
                .then(function (r) { return r.json(); })
                .then(function (cfg) {
                    setVal('cfg-model-extract', cfg.model_extract);
                    setVal('cfg-model-fallback', cfg.model_fallback);
                    setVal('cfg-model-cheap', cfg.model_cheap);
                    setVal('cfg-model-email', cfg.model_email);
                })
                .catch(function () {});
        })
        .catch(function () {
            // Fallback to basic models if API fails
            var fallbackModels = [
                {id: 'gpt-4o-mini', name: 'GPT-4o mini', provider: 'openai'},
                {id: 'gpt-4o-2024-11-20', name: 'GPT-4o', provider: 'openai'},
                {id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'anthropic'},
                {id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', provider: 'anthropic'},
                {id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', provider: 'anthropic'},
            ];
            ['cfg-model-extract', 'cfg-model-fallback', 'cfg-model-cheap', 'cfg-model-email'].forEach(function(id) {
                var sel = document.getElementById(id);
                if (!sel) return;
                sel.innerHTML = '<option value="">Sin modelos disponibles</option>';
                fallbackModels.forEach(function(m) {
                    var opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name + ' [' + m.provider + ']';
                    sel.appendChild(opt);
                });
            });
        });
}

function populateModelSelect(selectId, models) {
    var sel = document.getElementById(selectId);
    var searchInput = document.getElementById(selectId + '-search');
    if (!sel) return;

    // Store all models on the select for filtering
    sel._allModels = models;

    // Render options
    renderModelOptions(sel, models, '');

    // Show search input if more than 10 models
    if (searchInput) {
        if (models.length > 10) {
            searchInput.classList.remove('hidden');
        } else {
            searchInput.classList.add('hidden');
        }

        // Remove old listener and add new one
        searchInput._listener && searchInput.removeEventListener('input', searchInput._listener);
        var handler = function () {
            renderModelOptions(sel, sel._allModels, this.value.toLowerCase());
        };
        searchInput.addEventListener('input', handler);
        searchInput._listener = handler;
    }
}

function renderModelOptions(sel, models, filter) {
    var selectedVal = sel.value;
    sel.innerHTML = '';

    var emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = '— Seleccionar modelo —';
    sel.appendChild(emptyOpt);

    var count = 0;
    models.forEach(function (m) {
        var label = m.name + (m.provider ? ' [' + m.provider + ']' : '');
        if (filter && label.toLowerCase().indexOf(filter) === -1 && m.id.toLowerCase().indexOf(filter) === -1) {
            return;
        }
        var opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = label;
        sel.appendChild(opt);
        count++;
    });

    if (count === 0 && filter) {
        sel.innerHTML = '<option value="">Sin resultados para "' + filter + '"</option>';
    }

    if (selectedVal) {
        sel.value = selectedVal;
    }
}

/* ============== Card Modal (new card detection) ============== */
function initCardModal() {
    var modal = document.getElementById('card-modal');
    if (!modal) return;
    var saveBtn = document.getElementById('modal-save');
    var cancelBtn = document.getElementById('modal-cancel');

    cancelBtn.addEventListener('click', function () { modal.classList.add('hidden'); });
    modal.addEventListener('click', function (e) {
        if (e.target === modal) modal.classList.add('hidden');
    });

    saveBtn.addEventListener('click', function () {
        var responsable = document.getElementById('modal-responsable').value.trim();
        var email = document.getElementById('modal-email').value.trim();
        if (!responsable || !email) {
            showToast('Completá todos los campos', 'warning');
            return;
        }
        fetch('/api/config/cards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_suffix: window._newCardSuffix,
                card_type: window._newCardType || 'VISA',
                responsable: responsable,
                email: email
            })
        })
            .then(function (res) {
                if (!res.ok) throw new Error('Error al guardar');
                return res.json();
            })
            .then(function () {
                modal.classList.add('hidden');
                showToast('Tarjeta asignada correctamente', 'success');
            })
            .catch(function (err) {
                showToast(err.message, 'error');
            });
    });
}

function showCardModal(cardSuffix) {
    var modal = document.getElementById('card-modal');
    if (!modal) return;
    window._newCardSuffix = cardSuffix;
    window._newCardType = 'VISA';
    document.getElementById('card-modal-info').textContent =
        'Nueva tarjeta VISA terminada en ' + cardSuffix + ' — asigná un responsable';
    document.getElementById('modal-responsable').value = '';
    document.getElementById('modal-email').value = '';
    modal.classList.remove('hidden');
}

/* ============== Preview ============== */
function initPreview() {
    var btnPreview = document.getElementById('btn-preview-facturas');
    var btnSave = document.getElementById('btn-preview-save');
    var btnExcel = document.getElementById('btn-preview-excel');

    if (btnPreview) {
        btnPreview.addEventListener('click', fetchPreviewData);
    }
    if (btnSave) {
        btnSave.addEventListener('click', savePreviewData);
    }
    if (btnExcel) {
        btnExcel.addEventListener('click', downloadPreviewExcel);
    }
}

function fetchPreviewData() {
    var container = document.getElementById('preview-container');
    var loading = document.getElementById('preview-loading');
    var errorDiv = document.getElementById('preview-error');
    var tableContainer = document.getElementById('preview-table-container');
    var actions = document.getElementById('preview-actions');
    var tbody = document.getElementById('preview-tbody');
    var progressCount = document.getElementById('preview-progress-count');
    var btnPreview = document.getElementById('btn-preview-facturas');

    if (!window._selectedFolderId) {
        showToast('Seleccioná una carpeta de Drive primero', 'warning');
        return;
    }

    container.classList.remove('hidden');
    loading.classList.remove('hidden');
    errorDiv.classList.add('hidden');
    tableContainer.classList.add('hidden');
    actions.classList.add('hidden');
    tbody.innerHTML = '';
    btnPreview.disabled = true;

    var selectedIds = getSelectedFileIds();
    if (progressCount) progressCount.textContent = selectedIds.length > 0 ? selectedIds.length : 'todos';

    var body = {
        folder_id: window._selectedFolderId
    };
    if (selectedIds.length > 0) {
        body.file_ids = selectedIds;
    }

    fetch('/api/process/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (err) {
                    throw new Error(err.detail || 'Error al obtener vista previa');
                });
            }
            return res.json();
        })
        .then(function (data) {
            loading.classList.add('hidden');
            btnPreview.disabled = false;

            if (data.facturas && data.facturas.length > 0) {
                renderPreviewTable(data.facturas);
            } else {
                errorDiv.textContent = 'No se encontraron facturas en la carpeta seleccionada.';
                errorDiv.classList.remove('hidden');
            }
        })
        .catch(function (err) {
            loading.classList.add('hidden');
            btnPreview.disabled = false;
            errorDiv.textContent = err.message;
            errorDiv.classList.remove('hidden');
            showToast(err.message, 'error');
        });
}

function renderPreviewTable(facturas) {
    var tbody = document.getElementById('preview-tbody');
    var tableContainer = document.getElementById('preview-table-container');
    var actions = document.getElementById('preview-actions');

    tbody.innerHTML = '';

    facturas.forEach(function (f, idx) {
        var datos = f.datos || {};
        var estado = f.error ? 'error' : (datos.monto_total && datos.fecha && datos.emisor ? 'completo' : 'incompleto');

        var estadoBadge = '';
        if (estado === 'completo') {
            estadoBadge = '<span class="preview-badge-ok">Completo</span>';
        } else if (estado === 'incompleto') {
            estadoBadge = '<span class="preview-badge-warn">Incompleto</span>';
        } else {
            estadoBadge = '<span class="preview-badge-error">Error</span>';
        }

        var metodoBadge = '';
        var metodo = f.extraction_method || '';
        if (metodo === 'markitdown') {
            metodoBadge = '<span class="preview-badge-blue">MarkItDown</span>';
        } else if (metodo === 'vision' || metodo === 'vision_fallback') {
            metodoBadge = '<span class="preview-badge-purple">' + (metodo === 'vision_fallback' ? 'Vision fallback' : 'Vision') + '</span>';
        } else {
            metodoBadge = '<span class="text-xs text-gray-400">' + escapeHtml(metodo) + '</span>';
        }

        var tr = document.createElement('tr');
        tr.setAttribute('data-idx', idx);
        tr.setAttribute('data-drive-file-id', f.drive_file_id);

        if (f.error) {
            tr.innerHTML =
                '<td class="text-sm text-gray-800">' + escapeHtml(f.drive_file_name || '') + '</td>' +
                '<td>' + metodoBadge + '</td>' +
                '<td colspan="7" class="text-sm text-red-600">' + escapeHtml(f.error) + '</td>';
            tbody.appendChild(tr);
            return;
        }

        var monto = datos.monto_total != null ? datos.monto_total : '';
        var moneda = datos.moneda || 'ARS';
        var fecha = datos.fecha || '';
        var emisor = datos.emisor || '';
        var nroFactura = datos.numero_factura || '';
        var tipo = datos.tipo_factura || '';
        var cuota = datos.cuota_numero != null ? datos.cuota_numero : '';

        tr.innerHTML =
            '<td class="text-sm text-gray-800">' + escapeHtml(f.drive_file_name || '') + '</td>' +
            '<td>' + metodoBadge + '</td>' +
            '<td><input type="number" step="0.01" class="preview-input preview-monto text-right" value="' + monto + '" data-idx="' + idx + '"></td>' +
            '<td><select class="preview-input preview-moneda" data-idx="' + idx + '">' +
            '<option value="ARS"' + (moneda === 'ARS' ? ' selected' : '') + '>ARS</option>' +
            '<option value="USD"' + (moneda === 'USD' ? ' selected' : '') + '>USD</option>' +
            '</select></td>' +
            '<td><input type="text" class="preview-input preview-fecha" placeholder="DD/MM/YYYY" value="' + escapeHtml(fecha) + '" data-idx="' + idx + '"></td>' +
            '<td><input type="text" class="preview-input preview-emisor" value="' + escapeHtml(emisor) + '" data-idx="' + idx + '"></td>' +
            '<td><input type="text" class="preview-input preview-nro-factura" value="' + escapeHtml(nroFactura) + '" data-idx="' + idx + '"></td>' +
            '<td><select class="preview-input preview-tipo" data-idx="' + idx + '">' +
            '<option value="">—</option>' +
            '<option value="A"' + (tipo === 'A' ? ' selected' : '') + '>A</option>' +
            '<option value="B"' + (tipo === 'B' ? ' selected' : '') + '>B</option>' +
            '<option value="C"' + (tipo === 'C' ? ' selected' : '') + '>C</option>' +
            '<option value="comprobante_pago"' + (tipo === 'comprobante_pago' ? ' selected' : '') + '>Comp. Pago</option>' +
            '<option value="null"' + (tipo === '' || tipo === 'null' ? ' selected' : '') + '>N/A</option>' +
            '</select></td>' +
            '<td class="text-center"><input type="number" min="1" class="preview-input preview-cuota w-16 text-center" value="' + cuota + '" data-idx="' + idx + '"></td>' +
            '<td class="text-center">' + estadoBadge + '</td>';

        tr._originalData = {
            monto_total: datos.monto_total,
            moneda: datos.moneda,
            fecha: datos.fecha,
            emisor: datos.emisor,
            numero_factura: datos.numero_factura,
            tipo_factura: datos.tipo_factura,
            cuota_numero: datos.cuota_numero
        };

        tbody.appendChild(tr);
    });

    tableContainer.classList.remove('hidden');
    actions.classList.remove('hidden');
}

function collectPreviewData() {
    var facturas = [];
    var rows = document.querySelectorAll('#preview-tbody tr');
    var hasError = false;

    rows.forEach(function (tr) {
        var driveFileId = tr.getAttribute('data-drive-file-id');
        if (!driveFileId) return;

        var montoInput = tr.querySelector('.preview-monto');
        var monedaSelect = tr.querySelector('.preview-moneda');
        var fechaInput = tr.querySelector('.preview-fecha');
        var emisorInput = tr.querySelector('.preview-emisor');
        var nroFacturaInput = tr.querySelector('.preview-nro-factura');
        var tipoSelect = tr.querySelector('.preview-tipo');
        var cuotaInput = tr.querySelector('.preview-cuota');

        if (!montoInput) return;

        montoInput.classList.remove('preview-input-error');
        fechaInput.classList.remove('preview-input-error');
        emisorInput.classList.remove('preview-input-error');

        var monto = parseFloat(montoInput.value);
        var fecha = fechaInput.value.trim();
        var emisor = emisorInput.value.trim();

        var errors = [];
        if (isNaN(monto)) {
            errors.push('Monto inválido en ' + driveFileId);
            montoInput.classList.add('preview-input-error');
        }
        if (!fecha) {
            errors.push('Fecha vacía en ' + driveFileId);
            fechaInput.classList.add('preview-input-error');
        }
        if (!emisor) {
            errors.push('Emisor vacío en ' + driveFileId);
            emisorInput.classList.add('preview-input-error');
        }

        if (errors.length > 0) {
            hasError = true;
            return;
        }

        var cuotaVal = cuotaInput.value.trim();
        var cuotaNumero = cuotaVal !== '' ? parseInt(cuotaVal, 10) : null;
        if (cuotaNumero !== null && (isNaN(cuotaNumero) || cuotaNumero < 1)) {
            cuotaNumero = null;
        }

        var tipoVal = tipoSelect.value;
        if (tipoVal === 'null' || tipoVal === '') {
            tipoVal = null;
        }

        facturas.push({
            drive_file_id: driveFileId,
            monto_total: monto,
            moneda: monedaSelect.value,
            fecha: fecha,
            emisor: emisor,
            numero_factura: nroFacturaInput.value.trim(),
            tipo_factura: tipoVal,
            cuota_numero: cuotaNumero
        });
    });

    return { facturas: facturas, hasError: hasError };
}

function savePreviewData() {
    var btnSave = document.getElementById('btn-preview-save');
    var btnPreview = document.getElementById('btn-preview-facturas');

    var collected = collectPreviewData();
    if (collected.hasError) {
        showToast('Corregí los campos marcados en rojo antes de guardar', 'error');
        return;
    }
    if (collected.facturas.length === 0) {
        showToast('No hay facturas para guardar', 'warning');
        return;
    }

    btnSave.disabled = true;
    btnSave.textContent = 'Guardando...';

    var body = {
        resumen_id: window._resumenId,
        periodo: window._uploadPeriodo || '',
        folder_id: window._selectedFolderId,
        facturas: collected.facturas
    };

    fetch('/api/process/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (err) {
                    throw new Error(err.detail || 'Error al guardar facturas');
                });
            }
            return res.json();
        })
        .then(function (data) {
            showToast(data.saved + ' facturas guardadas correctamente', 'success');
            btnSave.disabled = true;
            btnPreview.disabled = true;
            btnSave.textContent = 'Guardado ✓';
            document.getElementById('btn-preview-excel').classList.remove('hidden');

            if (data.factura_ids && data.factura_ids.length > 0) {
                window._facturaIds = data.factura_ids;
            }
        })
        .catch(function (err) {
            btnSave.disabled = false;
            btnSave.textContent = 'Guardar y continuar';
            showToast('Error al guardar: ' + err.message, 'error');
        });
}

function downloadPreviewExcel() {
    if (!window._selectedFolderId) {
        showToast('Seleccioná una carpeta de Drive primero', 'warning');
        return;
    }
    var url = '/api/process/preview/excel?folder_id=' + encodeURIComponent(window._selectedFolderId);
    window.open(url, '_blank');
}

/* ============== Add Card Modal (config page) ============== */
function initAddCardModal() {
    var btn = document.getElementById('btn-add-card');
    var modal = document.getElementById('add-card-modal');
    var saveBtn = document.getElementById('add-card-save');
    var cancelBtn = document.getElementById('add-card-cancel');

    if (!btn || !modal) return;

    btn.addEventListener('click', function () { modal.classList.remove('hidden'); });

    cancelBtn.addEventListener('click', function () { modal.classList.add('hidden'); });
    modal.addEventListener('click', function (e) {
        if (e.target === modal) modal.classList.add('hidden');
    });

    saveBtn.addEventListener('click', function () {
        var cardNumber = document.getElementById('add-card-number').value.trim();
        var user = document.getElementById('add-card-user').value.trim();
        var email = document.getElementById('add-card-email').value.trim();
        if (!cardNumber || !user || !email) {
            showToast('Completá todos los campos', 'warning');
            return;
        }
        fetch('/api/config/cards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_suffix: cardNumber,
                card_type: 'VISA',
                responsable: user,
                email: email
            })
        })
            .then(function (res) {
                if (!res.ok) throw new Error('Error al guardar');
                return res.json();
            })
            .then(function () {
                modal.classList.add('hidden');
                document.getElementById('add-card-number').value = '';
                document.getElementById('add-card-user').value = '';
                document.getElementById('add-card-email').value = '';
                loadConfig();
                showToast('Tarjeta agregada correctamente', 'success');
            })
            .catch(function (err) {
                showToast(err.message, 'error');
            });
    });
}
