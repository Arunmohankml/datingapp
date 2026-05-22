/**
 * Replaces native <select> dropdowns with a styled app-like picker.
 * Opt out: <select data-native-select="true">
 */
(function () {
  function shouldSkip(select) {
    if (!select || select.tagName !== 'SELECT') return true;
    if (select.dataset.nativeSelect === 'true') return true;
    if (select.closest('.app-select')) return true;
    return false;
  }

  function enhanceSelect(select) {
    if (shouldSkip(select)) return;

    const wrap = document.createElement('div');
    wrap.className = 'app-select';
    if (select.disabled) wrap.classList.add('is-disabled');
    if (select.classList.contains('filter-select')) wrap.classList.add('app-select--compact');
    if (select.classList.contains('campus-select')) wrap.classList.add('app-select--modal');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'app-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');

    const valueEl = document.createElement('span');
    valueEl.className = 'app-select-value';

    const chevron = document.createElement('span');
    chevron.className = 'app-select-chevron';
    chevron.innerHTML = '<i class="fas fa-chevron-down"></i>';

    const list = document.createElement('div');
    list.className = 'app-select-list';
    list.setAttribute('role', 'listbox');

    function syncLabel() {
      const opt = select.options[select.selectedIndex];
      const text = opt ? opt.text.trim() : '';
      valueEl.textContent = text || select.getAttribute('data-placeholder') || 'Select…';
      valueEl.classList.toggle('is-placeholder', !select.value);
    }

    function buildList() {
      list.innerHTML = '';
      Array.from(select.options).forEach(function (opt) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'app-select-option';
        btn.textContent = opt.text;
        btn.dataset.value = opt.value;
        if (opt.disabled) btn.classList.add('is-disabled');
        if (opt.selected) btn.classList.add('is-selected');
        btn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (opt.disabled) return;
          select.value = opt.value;
          select.dispatchEvent(new Event('change', { bubbles: true }));
          syncLabel();
          list.querySelectorAll('.app-select-option').forEach(function (el) {
            el.classList.toggle('is-selected', el.dataset.value === select.value);
          });
          close();
        });
        list.appendChild(btn);
      });
      syncLabel();
    }

    function open() {
      document.querySelectorAll('.app-select.is-open').forEach(function (el) {
        if (el !== wrap) el.classList.remove('is-open');
      });
      wrap.classList.add('is-open');
    }

    function close() {
      wrap.classList.remove('is-open');
    }

    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (select.disabled) return;
      if (wrap.classList.contains('is-open')) close();
      else open();
    });

    select.addEventListener('change', function () {
      syncLabel();
      list.querySelectorAll('.app-select-option').forEach(function (el) {
        el.classList.toggle('is-selected', el.dataset.value === select.value);
      });
    });

    select.classList.add('app-select-native');
    select.setAttribute('tabindex', '-1');
    select.setAttribute('aria-hidden', 'true');

    const parent = select.parentNode;
    parent.insertBefore(wrap, select);
    wrap.appendChild(select);
    trigger.appendChild(valueEl);
    trigger.appendChild(chevron);
    wrap.appendChild(trigger);
    wrap.appendChild(list);

    buildList();
  }

  function initAll(root) {
    var scope = root || document;
    scope.querySelectorAll('select').forEach(enhanceSelect);
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.app-select')) {
      document.querySelectorAll('.app-select.is-open').forEach(function (el) {
        el.classList.remove('is-open');
      });
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.app-select.is-open').forEach(function (el) {
        el.classList.remove('is-open');
      });
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initAll(); });
  } else {
    initAll();
  }

  window.enhanceAppSelects = initAll;
})();
