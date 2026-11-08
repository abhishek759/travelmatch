/* TravelMatch — global JS */

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.alert.alert-dismissible').forEach(function (el) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    }, 5000);
  });
});
