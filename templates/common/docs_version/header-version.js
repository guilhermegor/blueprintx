/* Insert the static code version into the header bar (.md-header), so it sits in the
   masthead without taking an extra row. The value comes from the `code-version` meta tag set
   by overrides/main.html (fed by mkdocs_hooks.on_config from pyproject.toml) — no mike, no
   gh-pages, works under plain `mkdocs serve`. Re-applied on Material instant navigation. */
(function () {
	function insertVersion() {
		var meta = document.querySelector('meta[name="code-version"]');
		if (!meta) {
			return;
		}
		var title = document.querySelector(".md-header__title");
		if (!title || title.querySelector(".md-header__version")) {
			return;
		}
		var span = document.createElement("span");
		span.className = "md-header__version";
		span.textContent = meta.getAttribute("content") || "";
		title.appendChild(span);
	}

	if (document.readyState !== "loading") {
		insertVersion();
	} else {
		document.addEventListener("DOMContentLoaded", insertVersion);
	}
	if (typeof window.document$ !== "undefined" && window.document$.subscribe) {
		window.document$.subscribe(insertVersion);
	}
})();
