jQuery(document).ready(function () {

                      $("#gp_subject").autocomplete( {
                        source: subjects,
                        formatItem: formatItem
                      });
                      $("#sg_subject").autocomplete( {
                        source: subjects,
                        formatItem: formatItem
                      });
                      $("#sg_group").autocomplete({
                        source: groups,
                        formatItem: formatItem
                      });
                    });
