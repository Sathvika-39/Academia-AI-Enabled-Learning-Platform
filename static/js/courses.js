document.addEventListener('DOMContentLoaded', () => {
    // === Filter Logic ===
    const filterBtns = document.querySelectorAll('.filter-btn');
    const courseCards = document.querySelectorAll('.course-card');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all
            filterBtns.forEach(b => b.classList.remove('active'));
            // Add active to clicked
            btn.classList.add('active');

            const filterValue = btn.getAttribute('data-filter');

            courseCards.forEach(card => {
                if (filterValue === 'all' || card.getAttribute('data-category') === filterValue) {
                    card.style.display = 'block';
                    // Re-trigger AOS animation if needed, or just fade in
                    card.classList.add('fade-in');
                } else {
                    card.style.display = 'none';
                    card.classList.remove('fade-in');
                }
            });
        });
    });

    // === Search Logic ===
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');

    function filterCourses() {
        const searchTerm = searchInput.value.toLowerCase();
        courseCards.forEach(card => {
            const title = card.querySelector('h3').innerText.toLowerCase();
            if (title.includes(searchTerm)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    searchBtn.addEventListener('click', filterCourses);
    searchInput.addEventListener('keyup', filterCourses);

    // === Modal Logic ===
    const modal = document.getElementById('courseModal');
    const closeModal = document.querySelector('.close-modal');
    const viewBtns = document.querySelectorAll('.view-details-btn');

    // Elements to update in modal
    const modalTitle = document.getElementById('modalTitle');
    const modalImg = document.getElementById('modalImg');
    const modalDesc = document.getElementById('modalDesc');
    const modalInstructor = document.getElementById('modalInstructor');
    const modalPrice = document.getElementById('modalPrice');

    viewBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const card = btn.closest('.course-card');

            // Extract data from card
            const title = card.querySelector('h3').innerText;
            const img = card.querySelector('img').src;
            const instructor = card.querySelector('.instructor-name').innerText;
            // const price = card.querySelector('.price-tag').innerText;
            const desc = card.getAttribute('data-desc') || "Unlock your potential with this comprehensive course designed to take you from beginner to expert.";

            // Update modal
            modalTitle.innerText = title;
            modalImg.src = img;
            modalInstructor.innerText = instructor;
            // modalPrice.innerText = price;
            modalDesc.innerText = desc;

            // Show modal
            modal.classList.add('show');
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        });
    });

    closeModal.addEventListener('click', () => {
        modal.classList.remove('show');
        document.body.style.overflow = 'auto';
    });

    window.addEventListener('click', (e) => {
        if (e.target == modal) {
            modal.classList.remove('show');
            document.body.style.overflow = 'auto';
        }
    });
});
