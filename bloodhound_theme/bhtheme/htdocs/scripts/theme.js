

$( function () {
    // Do not close dropdown menu if user clicks on form controls
    $('.dropdown-menu input, .dropdown-menu label, .dropdown-menu select')
        .click(function (e) { e.stopPropagation(); });
    
    // Install quick create box click handlers
    $('#qct-cancel').click(
        function() {
          $('#qct-box input').val('');
        }
      )
  })

