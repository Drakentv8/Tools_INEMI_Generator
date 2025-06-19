// Function to validate video URL (YouTube/TikTok only)
function isValidVideoUrl(url) {
    if (!url) return true; // allow empty (optional)
    const ytRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\//i;
    const tiktokRegex = /^(https?:\/\/)?(www\.)?tiktok\.com\//i;
    return ytRegex.test(url) || tiktokRegex.test(url);
}

// Function to handle form submission
async function handleSubmit(event) {
    event.preventDefault();
    // Validate video reference URL
    const videoInput = document.getElementById('video_reference');
    const errorMsg = document.getElementById('video-url-error');
    if (videoInput) {
        const url = videoInput.value.trim();
        if (!isValidVideoUrl(url)) {
            errorMsg.classList.remove('hidden');
            videoInput.classList.add('border-red-500');
            videoInput.focus();
            return;
        } else {
            errorMsg.classList.add('hidden');
            videoInput.classList.remove('border-red-500');
        }
    }
    // Show loading overlay
    document.getElementById('loadingOverlay').classList.remove('hidden');
    
    try {
        const formData = new FormData(event.target);
        
        // Send form data to server
        const response = await fetch('/generate_step', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.error) {
            alert(result.error);
            return;
        }
        
        // Update UI with results
        updateResultsUI(result);
        
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while generating content. Please try again.');
    } finally {
        // Hide loading overlay
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
}

// Function to update results UI
function updateResultsUI(result) {
    const resultsSection = document.getElementById('results');
    resultsSection.classList.remove('hidden');
    
    // Project info update removed because fields do not exist in HTML
    // Update video analysis if available
    if (result.video_analysis) {
        const videoAnalysisSection = document.querySelector('.result-section:nth-child(2)');
        if (videoAnalysisSection) {
            videoAnalysisSection.classList.remove('hidden');
            videoAnalysisSection.querySelector('[data-field="video_title"]').textContent = result.video_analysis.video_info.title;
            videoAnalysisSection.querySelector('[data-field="video_platform"]').textContent = result.video_analysis.video_info.platform;
            videoAnalysisSection.querySelector('#video-analysis').value = result.video_analysis.analysis;
        }
    }
    // Update other sections (VEO Prompt, Narration, Caption, CTA)
    updateSection('veo-prompt', result.veo_prompt);
    updateSection('narration', result.narration);
    updateSection('caption', result.caption);
    updateSection('cta', result.cta);
}

// Function to update individual section
function updateSection(sectionId, content) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.value = content;
    }
}

// Function to copy content to clipboard
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.select();
        document.execCommand('copy');
        
        // Show copy confirmation
        const button = element.parentElement.querySelector('button');
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check mr-1"></i> Copied!';
        setTimeout(() => {
            button.innerHTML = originalText;
        }, 2000);
    }
}

// Add event listeners when document is loaded
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', handleSubmit);
    }
});

// Fungsi generate per step
async function generateStep(step, loading) {
    // Update step aktif di loading overlay
    setActiveStep(step);
    const form = document.getElementById('generateForm');
    const fd = new FormData(form);
    fd.append('step', step);
    let resp = await fetch('/generate_step', { method: 'POST', body: fd });
    let data = await resp.json();
    if (data.success) {
        updateProgressBar(step, data.elapsed);
        updateEstimatedTime(data.all_status);
    }
    return data;
} 