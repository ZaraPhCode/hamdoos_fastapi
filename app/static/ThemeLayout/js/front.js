/**
 * 2022 liewebs - Prestashop module developers and website designers.
 *
 * NOTICE OF LICENSE
 *  @author liewebs <info@liewebs.com>
 *  @copyright 2022 www.liewebs.com - liewebs
 *  @version 6.x.x
 * 	@module SuperTinyMCE PRO
 */
 
 $(document).ready(function(){
    // Readmore plugin function
    $('button[id^="toggle_button_more_"]').on('click', function(){
        $('button#toggle_button_less_'+$(this).attr('data-target')).show();
        $('.'+$(this).attr('data-target')+'.text_hidden').slideDown(500);
        $(this).hide();    
    });
    $('button[id^="toggle_button_less_"]').on('click', function(){
        $('button#toggle_button_more_'+$(this).attr('data-target')).show();
        $('.'+$(this).attr('data-target')+'.text_hidden').slideUp(500);
        $(this).hide();    
    });
    
    // Open link on modal
    $('a.supertiny_link_lightbox').on('click', function(e){
        e.preventDefault();
        let url = $(this).attr('href');
        $('body').append('<div class="modal fade" id="supertiny_link_modal" tabindex="-1" role="dialog" aria-labelledby="supertiny_link_modal" aria-hidden="true"><div class="modal-dialog"><div class="modal-content"><iframe src="'+url+'" allowfullscreen="true" frameborder="0" height="500" width="100%"></iframe><div class="modal-footer"><button type="button" class="btn btn-danger" data-dismiss="modal">'+close_lightbox+'</button></div></div></div></div>');
        $('#supertiny_link_modal').modal('show'); 
    });
 });