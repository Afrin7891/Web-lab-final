// =========================================
// UniPlan - Main JavaScript
// =========================================


// ---------- Page Loaded ----------

document.addEventListener("DOMContentLoaded", function () {

    console.log("UniPlan JavaScript Loaded Successfully");


    // Initialize functions
    initializePasswordToggle();
    initializeDeleteConfirmation();
    initializeAutoHideAlerts();
    initializeTooltips();
    initializeDeadlineHighlight();

});


// =========================================
// 1. Password Show / Hide
// =========================================

function togglePassword(inputId, buttonId) {

    const passwordInput = document.getElementById(inputId);
    const button = document.getElementById(buttonId);

    if (!passwordInput) {
        return;
    }

    if (passwordInput.type === "password") {

        passwordInput.type = "text";

        if (button) {
            button.innerHTML = "🙈";
        }

    } else {

        passwordInput.type = "password";

        if (button) {
            button.innerHTML = "👁️";
        }

    }
}


function initializePasswordToggle() {

    const passwordButtons =
        document.querySelectorAll("[data-password-toggle]");

    passwordButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const inputId =
                button.getAttribute("data-password-toggle");

            togglePassword(inputId, button.id);

        });

    });

}


// =========================================
// 2. Delete Confirmation
// =========================================

function confirmDelete(message) {

    if (!message) {

        message =
            "Are you sure you want to delete this item?";

    }

    return confirm(message);
}


function initializeDeleteConfirmation() {

    const deleteButtons =
        document.querySelectorAll(".delete-confirm");

    deleteButtons.forEach(function (button) {

        button.addEventListener("click", function (event) {

            const message =
                button.getAttribute("data-message") ||
                "Are you sure you want to delete this item?";

            if (!confirm(message)) {

                event.preventDefault();

            }

        });

    });

}


// =========================================
// 3. Auto Hide Flash Messages
// =========================================

function initializeAutoHideAlerts() {

    const alerts =
        document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {

        // Don't automatically hide important alerts
        if (
            alert.classList.contains("alert-danger") ||
            alert.classList.contains("alert-warning")
        ) {
            return;
        }

        setTimeout(function () {

            alert.style.transition =
                "opacity 0.5s ease";

            alert.style.opacity = "0";

            setTimeout(function () {

                alert.remove();

            }, 500);

        }, 5000);

    });

}


// =========================================
// 4. Bootstrap Tooltips
// =========================================

function initializeTooltips() {

    if (
        typeof bootstrap !== "undefined" &&
        bootstrap.Tooltip
    ) {

        const tooltipElements =
            document.querySelectorAll(
                '[data-bs-toggle="tooltip"]'
            );

        tooltipElements.forEach(function (element) {

            new bootstrap.Tooltip(element);

        });

    }

}


// =========================================
// 5. Deadline Highlight
// =========================================

function initializeDeadlineHighlight() {

    const deadlineElements =
        document.querySelectorAll(
            "[data-deadline-status]"
        );

    deadlineElements.forEach(function (element) {

        const status =
            element.getAttribute(
                "data-deadline-status"
            );

        if (!status) {
            return;
        }

        if (
            status.includes("Overdue") ||
            status.includes("Today")
        ) {

            element.classList.add(
                "deadline-danger"
            );

        } else if (
            status.includes("Tomorrow")
        ) {

            element.classList.add(
                "deadline-warning"
            );

        } else {

            element.classList.add(
                "deadline-success"
            );

        }

    });

}


// =========================================
// 6. Search Clear
// =========================================

function clearSearch(inputId) {

    const input =
        document.getElementById(inputId);

    if (input) {

        input.value = "";

        input.focus();

    }

}


// =========================================
// 7. Prevent Double Form Submission
// =========================================

document.addEventListener(
    "submit",
    function (event) {

        const form = event.target;

        if (!form || form.tagName !== "FORM") {
            return;
        }

        const submitButton =
            form.querySelector(
                'button[type="submit"]'
            );

        if (!submitButton) {
            return;
        }

        // Don't disable GET filter forms
        if (
            form.method.toLowerCase() === "get"
        ) {
            return;
        }

        setTimeout(function () {

            submitButton.disabled = true;

            const originalText =
                submitButton.innerHTML;

            submitButton.innerHTML =
                '<span class="spinner-border spinner-border-sm me-1"></span> Processing...';

            // Safety reset
            setTimeout(function () {

                submitButton.disabled = false;

                submitButton.innerHTML =
                    originalText;

            }, 5000);

        }, 50);

    }
);


// =========================================
// 8. Progress Animation
// =========================================

function animateProgressBars() {

    const progressBars =
        document.querySelectorAll(
            ".progress-bar"
        );

    progressBars.forEach(function (bar) {

        const targetWidth =
            bar.style.width;

        bar.style.width = "0%";

        setTimeout(function () {

            bar.style.width =
                targetWidth;

        }, 150);

    });

}


document.addEventListener(
    "DOMContentLoaded",
    function () {

        animateProgressBars();

    }
);


// =========================================
// 9. Current Year
// =========================================

function setCurrentYear() {

    const yearElements =
        document.querySelectorAll(
            ".current-year"
        );

    const currentYear =
        new Date().getFullYear();

    yearElements.forEach(function (element) {

        element.textContent =
            currentYear;

    });

}


document.addEventListener(
    "DOMContentLoaded",
    setCurrentYear
);


// =========================================
// 10. Back to Top Button
// =========================================

function createBackToTopButton() {

    const button =
        document.createElement("button");

    button.innerHTML = "↑";

    button.id = "backToTop";

    button.title = "Back to Top";

    button.style.position = "fixed";
    button.style.bottom = "25px";
    button.style.right = "25px";
    button.style.width = "45px";
    button.style.height = "45px";
    button.style.border = "none";
    button.style.borderRadius = "50%";
    button.style.backgroundColor = "#0d6efd";
    button.style.color = "white";
    button.style.fontSize = "20px";
    button.style.fontWeight = "bold";
    button.style.cursor = "pointer";
    button.style.display = "none";
    button.style.zIndex = "9999";
    button.style.boxShadow =
        "0 4px 12px rgba(0,0,0,0.2)";

    document.body.appendChild(button);


    window.addEventListener(
        "scroll",
        function () {

            if (window.scrollY > 300) {

                button.style.display =
                    "block";

            } else {

                button.style.display =
                    "none";

            }

        }
    );


    button.addEventListener(
        "click",
        function () {

            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });

        }
    );

}


document.addEventListener(
    "DOMContentLoaded",
    createBackToTopButton
);


// =========================================
// UniPlan JavaScript Completed
// =========================================