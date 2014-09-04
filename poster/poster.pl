#!/usr/bin/perl

#use strict;
#use warnings;
#require encoding;
#import encoding('cp1251', 'STDOUT' => 'cp1251');
#import encoding('ibm866', 'STDOUT' => 'ibm866');
require TswNetConf;
require TswNetwork;

die "Usage: poster.pl <contest-id> <team> <password>\nError" unless @ARGV == 3;
my $contestId = $ARGV[0];
my $teamId = $ARGV[1];
my $password = $ARGV[2];

my $MON = openChannel('MONITOR', 1);

my $time = time();
my $request = {
  Team => $teamId,
  Password => $password,
  ContestId => $contestId
};
sendChannel($MON, $request);

selectChannels(TswNetConf.$Timeout, $MON);

my $ans = doreadChannel($MON); 
my $error = $ans->{'Error'} if defined $ans->{'Error'};
my $ans0 = $ans if ($ans->{'ID'} eq $request->{'ID'});

closeChannel ($MON);

die "*** could not connect to testsys ***" unless defined $ans0;
die "*** testsys returned error: $error ***" if $error;
die "*** no monitor availible ***" unless defined $ans0->{'Monitor'} || defined $ans0->{'History'};

my $monitor = $ans0->{'Monitor'};
my $history = $ans0->{'History'};

print($monitor);
print("\x1a\n");
print($history);

1;
