/* ==========================================================================
   RIDGEWATCH Admin Dashboard — Legacy Controller (Redirects to testing.js)
   Direct access — zero authentication required.
   ========================================================================== */

(() => {
  "use strict";
  if (window.location.pathname.endsWith("admin.html")) {
    window.location.replace("testing.html");
  }
})();
