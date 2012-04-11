

$( function () {
    //$('#qct-newticket').popover({});
    
    // Do not close dropdown menu if user interacts with form controls
    $('.dropdown-menu input, .dropdown-menu label, .dropdown-menu select')
        .click(function (e) { e.stopPropagation(); });

    /* Helper functions */

    // Display message triggered by quick create box
    function qct_alert(msg) {
      alert(msg);
    }

    // Clear input controls inside quick create box
    function qct_clearui() {
      $('#qct-fieldset input, #qct-fieldset select').val('');
    }

    // Install quick create box click handlers
    $('#qct-cancel').click(
        function () {
          qct_clearui();
        }
      );
    $('#qct-create').click(
        function() {
          var qct_url = $('#qct-create').attr('data-target');
          $.post(qct_url, $('#qct-form').serialize(), 
              function(ticket_id) {
                qct_alert('Created ticket ' + ticket_id);
              })
              .error(function(jqXHR, textStatus, errorMsg) {
                  var msg = 'Error:' + errorMsg;
                  if (textStatus === 'timeout')
                    msg = 'Request timed out';
                  else if (textStatus === 'error')
                    msg = 'Could not create ticket . Error : ' + errorMsg;
                  else if (textStatus === 'abort')
                    msg = 'Aborted request'
                  qct_alert(msg);
                });
          qct_clearui();
        }
      )
  })

