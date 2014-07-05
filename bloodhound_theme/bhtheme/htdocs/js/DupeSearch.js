$(document).ready(function() {

	$('div#content.ticket h2#vc-summary').blur(function() {
		var text = $('div#content.ticket h2#vc-summary').text();
		if (text.length > 0) {

			var html = '<h5 class="loading">Loading related tickets..</h5>';
			var dupeticketlistDiv = $('div#content.ticket h2#vc-summary + div#dupeticketlist');
			if (dupeticketlistDiv.length == 0) {
				$('div#content.ticket h2#vc-summary').after('<div id="dupeticketlist" style="display:none;"></div>');
				dupeticketlistDiv = $('div#content.ticket h2#vc-summary + div#dupeticketlist');
			}
			$('ul',dupeticketlistDiv).slideUp('fast');
			dupeticketlistDiv.html(html).slideDown();

			$.ajax({
				url:'duplicate_ticket_search',
                data:{q:text},
				type:'GET',

				success: function(data, status) {
					var tickets =data;
					var ticketBaseHref =  'ticket/';
					var searchBaseHref =  'bhsearch?type=ticket&q=';
					var maxTickets = 15;

					var html = '';
					if (tickets === null) {
						// error
						dupeticketlistDiv.html('<h5 class="error">Error loading tickets.</h5>');
					} else if (tickets.length <= 0) {
						// no dupe tickets
						dupeticketlistDiv.slideUp();
					} else {
						html = '<h5>Possible related tickets:</h5><ul style="display:none;">'
						tickets = tickets.reverse();

						for (var i = 0; i < tickets.length && i < maxTickets; i++) {
							var ticket = tickets[i];
							html += '<li class="highlight_matches" title="' + ticket.description +
								    '"><a href="' + ticketBaseHref + ticket.url +
								    '"><span class="' + htmlencode(ticket.status) + '">#' +
								    ticket.url + '</span></a>: ' + htmlencode(ticket.type) + ': ' +
								    ticket.summary + '(' + htmlencode(ticket.status) +
								    (ticket.url ? ': ' + htmlencode(ticket.url) : '') +
								    ')' + '</li>'
						}
						html += '</ul>';
						if (tickets.length > maxTickets) {
							var text = $('div#content.ticket input#field-summary').val();
							html += '<a href="' + searchBaseHref + escape(text) + '">More..</a>';
						}

						dupeticketlistDiv.html(html);
						$('> ul', dupeticketlistDiv).slideDown();

					}

				},
				error: function(xhr, textStatus, exception) {
					dupeticketlistDiv.html('<h5 class="error">Error loading tickets: ' + textStatus + '</h5>');
				}
			});
		}
	});
	
	function htmlencode(text) {
		return $('<div/>').text(text).html().replace(/"/g, '&quot;').replace(/'/g, '&apos;');
	}
});
