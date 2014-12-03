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

$(function() {
  var qct_result = {};
  var qct_timeout = null;
  var grayed_out_controls = '#content, [role*="application"], #vc-summary, #inplace-propertyform, #attachments, .activityfeed, #help';


  // Do not close dropdown menu if user interacts with form controls
  $('.dropdown-menu input, .dropdown-menu label, .dropdown-menu select' +
    ', .dropdown-menu textarea').click(function(e) {
    e.stopPropagation();
  });

  function qct_inline_close() {
    $(grayed_out_controls).css('opacity', '');
    $('form:not("#qct-inline-form") :input').removeAttr('disabled');
    if ($('#qct-inline').is(':visible')) {
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

  function checkSelections() {
    return $.inArray('', $('#qct-box select[data-optional=false]').map(function() {
      return $(this).val();
    })) == -1;
  }

  $('#qct-create').attr("disabled", !checkSelections());
  $('#qct-box select').change(function() {
    $('#qct-create').attr("disabled", !checkSelections());
  });

  $('#qct-inline-newticket').click(function() {
    $('#qct-inline-notice-success, #qct-inline-notice-error').hide();

    if ($('#qct-inline').is(':visible')) {
      qct_inline_close();
    }
    else {
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
    title: function() {
      ticket = qct_info.ticket;
      if (ticket)
        title = _('Ticket #') + qct_info.ticket;
      else
        title = _('Error creating ticket');
      return title + ' <a class="close" id="qct-alert-close" ' +
          'data-dismiss="alert" href="#">&times;</a>'
    },
    content: function() {
      return qct_info.msg;
    }
  });

  /**
   * POST QCT form fields to full ticket form when "More fields" is clicked
   */
  function post_qct_more(e) {
    // As we're not creating the ticket, we'll remove hidden fields
    // that result in unnecessary validation messages.
    e.preventDefault();
    $qct_form = $('#qct-form');
    $qct_form.unbind('submit');
    new_ticket_url = $qct_form.find(':selected').attr('data-product-new-ticket-url');
    $qct_form.attr('action', new_ticket_url);
    $('.qct-product-scope-extra').remove();
    $qct_form.append('<input type="hidden" value="1" name="preview" />');
    $qct_form.submit();

  };

  function set_qct_more_enabled(is_enabled) {
    var qct_more = $('#qct-more');
    qct_more.unbind('click');
    if (is_enabled) {
      qct_more.removeClass('disabled');
      qct_more.click(post_qct_more);
    } else {
      qct_more.addClass('disabled');
      qct_more.click(function(e) {
        e.preventDefault();
        e.stopPropagation(); // keep #qct-form open
      });
    }
  }

  // Update QCT select fields on product change.
  $('#field-product').change(function(e) {
    set_qct_more_enabled($(this).val());
    $qct_form = $('#qct-form');
    var product = $qct_form.find('#field-product').val()
    if(product) {
      var form_token = $qct_form.find('input[name="__FORM_TOKEN"]').val();
      var fields_to_update = ['version', 'type'];
      $.post('update-menus', { product: product, __FORM_TOKEN: form_token,
          fields_to_update: fields_to_update }).done(function(data) {
        $.each(data, function(i, v) {
          $field = $('#field-' + i);
          $field.empty();
          $field.append('<option value="">Choose...</option>');
          $.each(v, function(i, v) {
            $field.append('<option value="' + v + '">' + v + '</option>');
          });

        });
      });
    }
  });

  set_qct_more_enabled($('#field-product').val());

  $('body').on('click.close', '#qct-alert-close',
      function(e) {
        qct_alert_close()
      });

  // Display & hide message triggered by quick create box
  function qct_alert(msg) {
    qct_info = msg;
    var link_content = '#' + qct_info.product + '-' + qct_info.ticket;
    var link = $(qct_info.msg).filter('a').html(link_content);
    $('#qct-last').empty()
        .append('Last ticket created: ')
        .append(link);
    $('#qct-last-container').show();
    $('#qct-newticket').popover('show');
    if (qct_timeout)
      clearTimeout(qct_timeout);
    qct_timeout = setTimeout(qct_alert_close, 4000);
  }

  function qct_alert_close() {
    jQuery('#qct-newticket').popover('hide');
  }

  // Clear input controls inside quick create box
  var timeout;
  $('#qct-newticket').click(function() {
    if (timeout) {
      clearTimeout(timeout);
    }
  });
  function qct_clearui() {
    $('#qct-form input[name!="__FORM_TOKEN"], #qct-form textarea').val('');
    $('#qct-inline-form input[name!="__FORM_TOKEN"], #qct-inline-form textarea').val('');
    $('#qct-create').attr("disabled", !checkSelections());
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(function() {
      $('#qct-form select').val('');
      $('#qct-inline-form select').val('');
      $('#qct-create').attr("disabled", !checkSelections());
    }, 120000);
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
      function() {
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
                product: ticket.product,
                msg: '<span class="alert alert-success">' +
                    _('Has been created') + '</span> ' +
                    '<a href="' + ticket.url + '">' + _('View / Edit') + '</a>'
              });
            })
            .error(function(jqXHR, textStatus, errorMsg) {
              var msg = 'Error:' + errorMsg;
              if (textStatus === 'timeout')
                msg = _('Request timed out');
              else if (textStatus === 'error')
                msg = _('Could not create ticket . Error : ') + errorMsg;
              else if (textStatus === 'abort')
                msg = _('Aborted request')
              qct_alert({
                ticket: null,
                msg: '<span class="alert alert-error"' +
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
          var msg = _('Ticket #') + ticket.id + _(' has been created. ');
          msg += '<a href="' + ticket.url + '">' + _('View / Edit') + '</a>';
          $('#qct-inline-notice-success span').html(msg);
          $('#qct-inline-notice-success').show({'duration': 400});
        })
        .error(function(jqXHR, textStatus, errorMsg) {
          var msg;
          if (textStatus === 'timeout')
            msg = _('Request timed out');
          else if (textStatus === 'error')
            msg = _('Could not create ticket. Error : ') + errorMsg;
          else if (textStatus === 'abort')
            msg = _('Aborted request');

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
    $spy.affix({ 'offset': $spy.position().top })
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
