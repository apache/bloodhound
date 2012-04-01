

$( function () {
    // Do not close dropdown menu if user clicks on form controls
    $('.dropdown-menu input, .dropdown-menu label')
        .click(function (e) { e.stopPropagation(); });
  })

