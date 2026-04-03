/**
 * main.js — Utilitários globais do Agenda Escolar
 */

/**
 * Retorna o token CSRF do formulário ou da meta tag.
 */
function getCsrfToken() {
  const input = document.querySelector('input[name="csrf_token"]');
  if (input) return input.value;
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

/**
 * Exibe uma mensagem toast temporária.
 */
function showToast(message, type = 'info', duration = 4000) {
  const colors = {
    success: 'bg-green-50 text-green-700 border-green-200',
    error: 'bg-red-50 text-red-700 border-red-200',
    warning: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    info: 'bg-blue-50 text-blue-700 border-blue-200',
  };
  const toast = document.createElement('div');
  toast.className = `fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg border text-sm font-medium transition-all ${colors[type] || colors.info}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

/**
 * Confirma antes de enviar formulários destrutivos.
 */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      const msg = el.dataset.confirm || 'Tem certeza?';
      if (!confirm(msg)) e.preventDefault();
    });
  });
});
