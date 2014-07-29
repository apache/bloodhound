jQuery(document).ready(function() {

	$('div#content.ticket h2#vc-summary').blur(function() {
		var text = $('div#content.ticket h2#vc-summary').text();
		if (text.length > 0) {

			var html = '<h5 class="loading">Loading related tickets..</h5>';
			var duplicate_eticket_list_div = $('div#content.ticket h2#vc-summary + div#dupeticketlist');
			if (duplicate_eticket_list_div.length == 0) {
				$('div#content.ticket h2#vc-summary').after('<div id="dupeticketlist" style="display:none;"></div>');
				duplicate_eticket_list_div = $('div#content.ticket h2#vc-summary + div#dupeticketlist');
			}
			$('ul',duplicate_eticket_list_div).slideUp('fast');
			duplicate_eticket_list_div.html(html).slideDown();

			$.ajax({
				url:'duplicate_ticket_search',
                data:{q:text},
				type:'GET',

				success: function(data, status) {
					var tickets =data;
					var ticket_base_Href =  'ticket/';
					var search_base_Href =  'bhsearch?type=ticket&q=';
					var max_tickets = 15;

					var html = '';
					if (tickets === null) {
						// error
						duplicate_eticket_list_div.html('<h5 class="error">Error loading tickets.</h5>');
					} else if (tickets.length <= 0) {
						// no dupe tickets
						duplicate_eticket_list_div.slideUp();
					} else {
						html = '<h5>Possible related tickets:</h5><ul id="results" style="display:none; list-style-type: none">'
						tickets = tickets.reverse();

						for (var i = 0; i < tickets.length && i < max_tickets; i++) {
							var ticket = tickets[i];
							html += '<li class="highlight_matches" title="' + ticket.description +
								    '"><a href="' + ticket_base_Href + ticket.url +
								    '"><span class="' + htmlencode(ticket.status) + '">#' +
								    ticket.url + '</span></a>: ' +
								    ticket.summary + ' (' + htmlencode(ticket.status)
								    +': '+ htmlencode(ticket.type) +
								    ') ' +'<span class="author">created by '+ticket.owner +'</span> <span class="date">at ' +ticket.date+ '</span></li>'
						}
						html += '</ul>';
						if (tickets.length > max_tickets) {
							var text = $('div#content.ticket input#field-summary').val();
							html += '<a href="' + search_base_Href + escape(text) + '">More..</a>';
						}

						duplicate_eticket_list_div.html(html);
						$('> ul', duplicate_eticket_list_div).slideDown();

					}

				},
				error: function(xhr, textStatus, exception) {
					duplicate_eticket_list_div.html('<h5 class="error">Error loading tickets: ' + textStatus + '</h5>');
				}
			});
		}else{
            var duplicate_eticket_list_div = $('div#content.ticket div#dupeticketlist');
            duplicate_eticket_list_div.slideUp('fast');
        }
	});
	
	function htmlencode(text) {
		return $('<div/>').text(text).html().replace(/"/g, '&quot;').replace(/'/g, '&apos;');
	}
});
