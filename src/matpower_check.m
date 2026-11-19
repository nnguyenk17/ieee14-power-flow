% MATPOWER check for the IEEE 14-bus case
% Author: Nguyen Nguyen
%
% Solves the same IEEE 14-bus load flow in MATPOWER (MATLAB) and prints the
% values I compare with my pandapower (Python) results.
%
% Run from the project root:   matlab -batch "run('src\matpower_check.m')"

mpopt = mpoption('verbose', 0, 'out.all', 0);   % run quietly, no full report
r = runpf('case14', mpopt);                      % solve the load flow

losses = sum(real(get_losses(r)));               % add up real power losses (MW)
fprintf('\n=== MATPOWER results (IEEE 14-bus) ===\n');
fprintf('Bus 14 voltage : %.4f pu\n', r.bus(14, 8));    % column 8 = voltage magnitude
fprintf('Bus 14 angle   : %.4f deg\n', r.bus(14, 9));   % column 9 = voltage angle
fprintf('Total losses   : %.2f MW\n', losses);
