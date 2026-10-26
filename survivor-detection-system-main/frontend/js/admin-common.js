/* ==========================================================================
   RIDGEWATCH admin-common.js — Compatibility Bridge to testing-common.js
   ========================================================================== */

(() => {
  "use strict";
  // If testing-common.js has already run, AdminCommon is already set.
  if (window.TestingCommon) {
    window.AdminCommon = window.TestingCommon;
  }
})();
