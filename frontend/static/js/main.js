// Modal helpers
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}
function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

// Close modal clicking outside
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.add('hidden');
  }
});

// Auto-dismiss alerts after 4s
document.querySelectorAll('.alert').forEach(function(el) {
  setTimeout(function() {
    el.style.transition = 'opacity .5s';
    el.style.opacity    = '0';
    setTimeout(function() { el.remove(); }, 500);
  }, 4000);
});