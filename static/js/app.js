(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileInfo = document.getElementById("file-info");
  const fileNameEl = document.getElementById("file-name");
  const clearFileBtn = document.getElementById("clear-file");
  const outputDirInput = document.getElementById("output-dir");
  const startBtn = document.getElementById("start-btn");
  const progressSection = document.getElementById("progress-section");
  const progressBar = document.getElementById("progress-bar");
  const progressText = document.getElementById("progress-text");
  const progressPercent = document.getElementById("progress-percent");
  const currentFileEl = document.getElementById("current-file");
  const logPanel = document.getElementById("log-panel");
  const resultActions = document.getElementById("result-actions");
  const downloadZipBtn = document.getElementById("download-zip");
  const downloadFailedBtn = document.getElementById("download-failed");
  const resultPathEl = document.getElementById("result-path");
  const browseDirBtn = document.getElementById("browse-dir");

  let selectedFile = null;
  let pollTimer = null;
  let lastLogCount = 0;

  function setFile(file) {
    if (!file) return;
    const ext = file.name.toLowerCase();
    if (!ext.endsWith(".xlsx") && !ext.endsWith(".xls")) {
      alert("仅支持 .xlsx / .xls 文件");
      return;
    }
    selectedFile = file;
    fileNameEl.textContent = file.name;
    fileInfo.classList.remove("hidden");
    dropZone.classList.add("hidden");
    startBtn.disabled = false;
  }

  function clearFile() {
    selectedFile = null;
    fileInput.value = "";
    fileInfo.classList.add("hidden");
    dropZone.classList.remove("hidden");
    startBtn.disabled = true;
  }

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    setFile(file);
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });

  clearFileBtn.addEventListener("click", clearFile);

  browseDirBtn.addEventListener("click", () => {
    alert("请输入本机绝对路径，例如：\nC:\\Users\\你的用户名\\Desktop\\output");
  });

  function appendLogs(logs) {
    const newLogs = logs.slice(lastLogCount);
    newLogs.forEach((entry) => {
      const div = document.createElement("div");
      div.className = "log-entry";
      div.innerHTML = `
        <span class="log-time">${entry.time}</span>
        <span class="log-message ${entry.level}">${escapeHtml(entry.message)}</span>
      `;
      logPanel.appendChild(div);
    });
    lastLogCount = logs.length;
    logPanel.scrollTop = logPanel.scrollHeight;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function updateProgress(data) {
    const { current, total, current_file: currentFile, logs } = data;
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;

    progressBar.style.width = `${pct}%`;
    progressText.textContent = `${current} / ${total}`;
    progressPercent.textContent = `${pct}%`;
    currentFileEl.textContent = currentFile ? `当前: ${currentFile}` : "";

    appendLogs(logs);
  }

  function showResult(data) {
    resultActions.classList.remove("hidden");
    downloadZipBtn.href = `/api/download/${data.id}/zip`;

    if (data.failed_count > 0 && data.failed_path) {
      downloadFailedBtn.classList.remove("hidden");
      downloadFailedBtn.href = `/api/download/${data.id}/failed`;
    }

    resultPathEl.textContent = `输出目录: ${data.output_dir}`;
    startBtn.disabled = false;
    startBtn.textContent = "重新开始";
  }

  async function pollStatus(jobId) {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      const data = await res.json();

      if (!res.ok) {
        clearInterval(pollTimer);
        alert(data.error || "获取状态失败");
        startBtn.disabled = false;
        return;
      }

      updateProgress(data);

      if (data.status === "completed") {
        clearInterval(pollTimer);
        showResult(data);
      } else if (data.status === "error") {
        clearInterval(pollTimer);
        alert(`任务失败: ${data.error}`);
        startBtn.disabled = false;
      }
    } catch (err) {
      clearInterval(pollTimer);
      alert(`网络错误: ${err.message}`);
      startBtn.disabled = false;
    }
  }

  startBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("output_dir", outputDirInput.value.trim());

    startBtn.disabled = true;
    startBtn.textContent = "下载中...";
    progressSection.classList.remove("hidden");
    resultActions.classList.add("hidden");
    downloadFailedBtn.classList.add("hidden");
    logPanel.innerHTML = "";
    lastLogCount = 0;
    progressBar.style.width = "0%";

    try {
      const res = await fetch("/api/start", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "启动失败");
        startBtn.disabled = false;
        startBtn.textContent = "开始下载";
        return;
      }

      pollTimer = setInterval(() => pollStatus(data.job_id), 800);
    } catch (err) {
      alert(`网络错误: ${err.message}`);
      startBtn.disabled = false;
      startBtn.textContent = "开始下载";
    }
  });
})();
