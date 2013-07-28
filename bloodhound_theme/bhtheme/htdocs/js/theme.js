/*
  Licensed to the Apache Software Foundation (ASF) under one
  or more contributor license agreements.  See the NOTICE file
  distributed with this work for additional information
  regarding copyright ownership.  The ASF licenses this file
  to you under the Apache License, Version 2.0 (the
  "License"); you may not use this file except in compliance
  with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
  KIND, either express or implied.  See the License for the
  specific language governing permissions and limitations
  under the License.
*/

$( function () {
    var qct_result = {};
    var qct_timeout = null;
    var grayed_out_controls = '#content, [role*="application"], #vc-summary, #inplace-propertyform, #attachments, .activityfeed, #help';


    // Do not close dropdown menu if user interacts with form controls
    $('.dropdown-menu input, .dropdown-menu label, .dropdown-menu select' +
        ', .dropdown-menu textarea').click(function (e) { e.stopPropagation(); });

    function qct_inline_close()
    {
      $(grayed_out_controls).css('opacity', '');
      $('form:not("#qct-inline-form") :input').removeAttr('disabled');
      if ($('#qct-inline').is(':visible'))
      {
        $('#qct-inline').hide({'duration': 400});
      }
    }

    // If the window is resized, close the inline form + re-enable
    // all other forms to prevent undesirable behaviour. For example,
    // resizing the window to a -desktop size when inline form is
    // shown would result in the form disappearing (ok), but all other
    // forms would still be disabled (not ok).
    // NOTE - currently disabled due to certain phones resizing the
    // window when the form controls are focused (e.g. input)
/*
    $(window).resize(function() {
      qct_inline_close();
    });
*/

    $('#qct-inline-newticket').click(function() {
      $('#qct-inline-notice-success, #qct-inline-notice-error').hide();

      if ($('#qct-inline').is(':visible'))
      {
        qct_inline_close();
      }
      else
      {
        $(grayed_out_controls).css('opacity', '0.3');
        $('form:not("#qct-inline-form") :input').attr('disabled', 'disabled');
        $('#qct-inline').show({'duration': 400});
        $('#inline-field-summary').focus();
      }
    });
    $('#qct-inline-cancel, #qct-inline-alert-cancel').click(qct_inline_close);


    // Install popover for create ticket shortcut
    // Important: Further options specified in markup
    $('#qct-newticket').popover({
        title : function () {
            ticket = qct_info.ticket;
            if (ticket)
              title = 'Ticket #' + qct_info.ticket;
            else
              title = 'Error creating ticket';
            return title + ' <a class="close" id="qct-alert-close" ' +
                'data-dismiss="alert" href="#">&times;</a>'
          },
        content : function () { return qct_info.msg; }
      });

    $('body').on('click.close', '#qct-alert-close', 
        function (e) { qct_alert_close() });

    // Display & hide message triggered by quick create box
    function qct_alert(msg) {
      qct_info = msg;
      jQuery('#qct-newticket').popover('show');
      if (qct_timeout)
        clearTimeout(qct_timeout);
      qct_timeout = setTimeout(qct_alert_close, 4000);
    }

    function qct_alert_close() {
      jQuery('#qct-newticket').popover('hide');
    }

    // Clear input controls inside quick create box
    function qct_clearui() {
      $('#qct-form input[name!="__FORM_TOKEN"], #qct-form select, #qct-form textarea').val('');
      $('#qct-inline-form input[name!="__FORM_TOKEN"], #qct-inline-form select, #qct-inline-form textarea').val('');
    }

    // We want to submit via #qct-create
    $('#qct-form').submit(function(e) {
      $('#qct-create').click();
      e.preventDefault();
    });
    $('#qct-inline-form').submit(function(e) {
      $('#qct-inline-create').click();
      e.preventDefault();
    });

    // Install quick create box click handlers
    $('#qct-cancel').click(
        function () {
          qct_clearui();
        }
      );
    $('#qct-create').click(
        function() {
          // data-target is the base url for the product in current scope
          var product_base_url = $('#qct-create').attr('data-target');
          if (product_base_url === '/')
            product_base_url = '';
          $.post(product_base_url + '/qct', $('#qct-form').serialize(),
              function(ticket) {
                qct_alert({
                    ticket: ticket.id,
                    msg: '<span class="alert alert-success">' +
                         'Has been created</span> ' +
                         '<a href="' + ticket.url + '">View / Edit</a>'
                  });
              })
              .error(function(jqXHR, textStatus, errorMsg) {
                  var msg = 'Error:' + errorMsg;
                  if (textStatus === 'timeout')
                    msg = 'Request timed out';
                  else if (textStatus === 'error')
                    msg = 'Could not create ticket . Error : ' + errorMsg;
                  else if (textStatus === 'abort')
                    msg = 'Aborted request'
                  qct_alert({ 
                      ticket : null, 
                      msg : '<span class="alert alert-error"' +
                          ' style="display:block">' + msg + '</span>'
                    });
                });
          qct_clearui();
        }
      );

    $('#qct-inline-create').click(function() {
      // data-target is the base url for the product in current scope
      var product_base_url = $('#qct-inline-create').attr('data-target');
      if (product_base_url === '/')
        product_base_url = '';
      $.post(product_base_url + '/qct', $('#qct-inline-form').serialize(),
          function(ticket) {
            var msg = 'Ticket #' + ticket.id + ' has been created. ';
            msg += '<a href="' + ticket.url + '">View / Edit</a>';
            $('#qct-inline-notice-success span').html(msg);
            $('#qct-inline-notice-success').show({'duration': 400});
          })
          .error(function(jqXHR, textStatus, errorMsg) {
            var msg;
            if (textStatus === 'timeout')
              msg = 'Request timed out';
            else if (textStatus === 'error')
              msg = 'Could not create ticket. Error : ' + errorMsg;
            else if (textStatus === 'abort')
              msg = 'Aborted request';

            $('#qct-inline-notice-error span').html(msg);
            $('#qct-inline-notice-error').show({'duration': 400});
          });

      qct_clearui();
      qct_inline_close();
      $('body').animate({scrollTop: 0}, 250);
    });
  })

// Event handlers for sticky panels , if any
function setup_sticky_panel(selector) {
  var target = $(selector);
  target.each(function() {
    var $spy = $(this);
    $spy.affix( { 'offset' : $spy.position().top } )
  });
  var h = target.height();
  target.parent('.stickyBox').height(h);

  target = h = null;
  $(window).on('scroll.affix.data-api', function() {
      var target = $(selector);
      var affix_data = target.data('affix');

      if (affix_data && !affix_data.affixed) {
        var h = target.height();
        target.parent('.stickyBox').height(h);
      }
      else {
        target.parent('.stickyBox').css('height', '');
      }
    })
  $(function() {
      var prev_onhashchange = window.onhashchange;

      window.onhashchange = function() {
        prev_onhashchange();
        var target = $(selector);
        var affix_data = target.data('affix');
    
        if (affix_data && !affix_data.affixed)
          window.scrollBy(0, -target.height());
      }
    })
}

