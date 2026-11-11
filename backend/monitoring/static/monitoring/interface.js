const navigationButton = document.querySelector(".nav-toggle");
const navigation = document.getElementById("app-navigation");
if (navigationButton && navigation) {
  document.body.classList.add("navigation-ready");
  navigationButton.hidden = false;
  const closeNavigation = () => {
    document.body.classList.remove("navigation-open");
    navigationButton.setAttribute("aria-expanded", "false");
  };
  navigationButton.addEventListener("click", () => {
    const open = document.body.classList.toggle("navigation-open");
    navigationButton.setAttribute("aria-expanded", String(open));
  });
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeNavigation();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("navigation-open")) {
      closeNavigation();
      navigationButton.focus();
    }
  });
}
document.querySelectorAll(".account-menu").forEach((menu) => {
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target)) menu.open = false;
  });
});
