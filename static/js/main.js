

$(document).ready(function() {

    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);


    $('[data-bs-toggle="tooltip"]').tooltip();


    $('.event-form').on('submit', function(e) {
        var startDateTime = new Date($('#start_datetime').val());
        var endDateTime = new Date($('#end_datetime').val());
        
        if (endDateTime <= startDateTime) {
            e.preventDefault();
            alert('End time must be after start time');
            return false;
        }
        
        return true;
    });


    $('#event-filter-form').on('submit', function(e) {
        e.preventDefault();
        
        var cause = $('#cause').val().toLowerCase();
        var location = $('#location').val().toLowerCase();
        var date = $('#date').val();
        
        $('.event-card').each(function() {
            var eventCause = $(this).data('cause').toLowerCase();
            var eventLocation = $(this).data('location').toLowerCase();
            var eventDate = $(this).data('date');
            
            var showEvent = true;
            
            if (cause && eventCause.indexOf(cause) === -1) {
                showEvent = false;
            }
            
            if (location && eventLocation.indexOf(location) === -1) {
                showEvent = false;
            }
            
            if (date && eventDate !== date) {
                showEvent = false;
            }
            
            if (showEvent) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });


    $('#reset-filters').on('click', function() {
        $('#cause').val('');
        $('#location').val('');
        $('#date').val('');
        $('.event-card').show();
    });


    $('.confirm-action').on('click', function(e) {
        if (!confirm('Are you sure you want to perform this action?')) {
            e.preventDefault();
            return false;
        }
        return true;
    });
});
