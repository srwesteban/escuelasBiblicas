/**
 * Carrusel de escuelas en inicio + modal de descripción.
 */
(function () {
    const section = document.querySelector('.inicio-escuelas-carousel');
    if (!section) return;

    const viewport = section.querySelector('.inicio-carousel-viewport');
    const prevBtn = section.querySelector('.inicio-carousel-btn--prev');
    const nextBtn = section.querySelector('.inicio-carousel-btn--next');
    const modal = document.getElementById('inicio-school-modal');
    const modalTitle = document.getElementById('inicio-school-modal-title');
    const modalBody = document.getElementById('inicio-school-modal-body');
    const modalClose = modal?.querySelector('[data-inicio-modal-close]');

    function scrollByCard(dir) {
        if (!viewport) return;
        const card = viewport.querySelector('.inicio-school-card');
        const w = card ? card.offsetWidth + 16 : 300;
        viewport.scrollBy({ left: dir * w, behavior: 'smooth' });
    }

    prevBtn?.addEventListener('click', () => scrollByCard(-1));
    nextBtn?.addEventListener('click', () => scrollByCard(1));

    function openModal(title, templateId) {
        if (!modal || !modalTitle || !modalBody) return;
        const tpl = templateId ? document.getElementById(templateId) : null;
        modalTitle.textContent = title;
        modalBody.innerHTML = '';
        if (tpl && tpl.content) {
            modalBody.appendChild(tpl.content.cloneNode(true));
        }
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        modalClose?.focus();
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    section.querySelectorAll('.inicio-school-card').forEach((btn) => {
        btn.addEventListener('click', () => {
            const title = btn.getAttribute('data-school-title') || '';
            const tid = btn.getAttribute('data-desc-template');
            openModal(title, tid);
        });
    });

    modalClose?.addEventListener('click', closeModal);
    modal?.querySelector('.inicio-school-modal__backdrop')?.addEventListener('click', closeModal);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
            closeModal();
        }
    });
})();
