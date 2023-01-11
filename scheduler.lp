\ Model shop_schedule
\ LP format - for model browsing. Use MPS format to capture full model detail.
Minimize
  10 s[Tom,0] + 10 s[Tom,1] + 10 s[Tom,2] + 10 s[Tom,3] + 10 s[Tom,4]
   + 10 s[Tom,5] + 10 s[Tom,6] + 10 s[Tom,7] + 10 s[Tom,8] + 10 s[Tom,9]
   + 10 s[Tom,10] + 10 s[Tom,11] + 10 s[Tom,12] + 10 s[Tom,13]
   + 15 s[Bri,0] + 15 s[Bri,1] + 15 s[Bri,2] + 15 s[Bri,3] + 15 s[Bri,4]
   + 15 s[Bri,5] + 15 s[Bri,6] + 15 s[Bri,7] + 15 s[Bri,8] + 15 s[Bri,9]
   + 15 s[Bri,10] + 15 s[Bri,11] + 15 s[Bri,12] + 15 s[Bri,13]
   + 16 s[Alex,0] + 16 s[Alex,1] + 16 s[Alex,2] + 16 s[Alex,3]
   + 16 s[Alex,4] + 16 s[Alex,5] + 16 s[Alex,6] + 16 s[Alex,7]
   + 16 s[Alex,8] + 16 s[Alex,9] + 16 s[Alex,10] + 16 s[Alex,11]
   + 16 s[Alex,12] + 16 s[Alex,13]
Subject To
 availability_for_Tom-0: avail[Tom,0] = 1
 availability_for_Tom-1: avail[Tom,1] = 1
 availability_for_Tom-2: avail[Tom,2] = 1
 availability_for_Tom-3: avail[Tom,3] = 1
 availability_for_Tom-4: avail[Tom,4] = 1
 availability_for_Tom-5: avail[Tom,5] = 1
 availability_for_Tom-6: avail[Tom,6] = 1
 availability_for_Tom-7: avail[Tom,7] = 1
 availability_for_Tom-8: avail[Tom,8] = 1
 availability_for_Tom-9: avail[Tom,9] = 1
 availability_for_Tom-10: avail[Tom,10] = 1
 availability_for_Tom-11: avail[Tom,11] = 1
 availability_for_Tom-12: avail[Tom,12] = 1
 availability_for_Tom-13: avail[Tom,13] = 1
 availability_for_Bri-0: avail[Bri,0] = 1
 availability_for_Bri-1: avail[Bri,1] = 1
 availability_for_Bri-2: avail[Bri,2] = 0
 availability_for_Bri-3: avail[Bri,3] = 1
 availability_for_Bri-4: avail[Bri,4] = 1
 availability_for_Bri-5: avail[Bri,5] = 1
 availability_for_Bri-6: avail[Bri,6] = 1
 availability_for_Bri-7: avail[Bri,7] = 1
 availability_for_Bri-8: avail[Bri,8] = 1
 availability_for_Bri-9: avail[Bri,9] = 0
 availability_for_Bri-10: avail[Bri,10] = 1
 availability_for_Bri-11: avail[Bri,11] = 1
 availability_for_Bri-12: avail[Bri,12] = 1
 availability_for_Bri-13: avail[Bri,13] = 1
 availability_for_Alex-0: avail[Alex,0] = 1
 availability_for_Alex-1: avail[Alex,1] = 1
 availability_for_Alex-2: avail[Alex,2] = 1
 availability_for_Alex-3: avail[Alex,3] = 1
 availability_for_Alex-4: avail[Alex,4] = 1
 availability_for_Alex-5: avail[Alex,5] = 1
 availability_for_Alex-6: avail[Alex,6] = 1
 availability_for_Alex-7: avail[Alex,7] = 1
 availability_for_Alex-8: avail[Alex,8] = 1
 availability_for_Alex-9: avail[Alex,9] = 1
 availability_for_Alex-10: avail[Alex,10] = 1
 availability_for_Alex-11: avail[Alex,11] = 1
 availability_for_Alex-12: avail[Alex,12] = 1
 availability_for_Alex-13: avail[Alex,13] = 1
 availability_constraint_for_Tom-0: s[Tom,0] - avail[Tom,0] <= 0
 availability_constraint_for_Tom-1: s[Tom,1] - avail[Tom,1] <= 0
 availability_constraint_for_Tom-2: s[Tom,2] - avail[Tom,2] <= 0
 availability_constraint_for_Tom-3: s[Tom,3] - avail[Tom,3] <= 0
 availability_constraint_for_Tom-4: s[Tom,4] - avail[Tom,4] <= 0
 availability_constraint_for_Tom-5: s[Tom,5] - avail[Tom,5] <= 0
 availability_constraint_for_Tom-6: s[Tom,6] - avail[Tom,6] <= 0
 availability_constraint_for_Tom-7: s[Tom,7] - avail[Tom,7] <= 0
 availability_constraint_for_Tom-8: s[Tom,8] - avail[Tom,8] <= 0
 availability_constraint_for_Tom-9: s[Tom,9] - avail[Tom,9] <= 0
 availability_constraint_for_Tom-10: s[Tom,10] - avail[Tom,10] <= 0
 availability_constraint_for_Tom-11: s[Tom,11] - avail[Tom,11] <= 0
 availability_constraint_for_Tom-12: s[Tom,12] - avail[Tom,12] <= 0
 availability_constraint_for_Tom-13: s[Tom,13] - avail[Tom,13] <= 0
 availability_constraint_for_Bri-0: s[Bri,0] - avail[Bri,0] <= 0
 availability_constraint_for_Bri-1: s[Bri,1] - avail[Bri,1] <= 0
 availability_constraint_for_Bri-2: s[Bri,2] - avail[Bri,2] <= 0
 availability_constraint_for_Bri-3: s[Bri,3] - avail[Bri,3] <= 0
 availability_constraint_for_Bri-4: s[Bri,4] - avail[Bri,4] <= 0
 availability_constraint_for_Bri-5: s[Bri,5] - avail[Bri,5] <= 0
 availability_constraint_for_Bri-6: s[Bri,6] - avail[Bri,6] <= 0
 availability_constraint_for_Bri-7: s[Bri,7] - avail[Bri,7] <= 0
 availability_constraint_for_Bri-8: s[Bri,8] - avail[Bri,8] <= 0
 availability_constraint_for_Bri-9: s[Bri,9] - avail[Bri,9] <= 0
 availability_constraint_for_Bri-10: s[Bri,10] - avail[Bri,10] <= 0
 availability_constraint_for_Bri-11: s[Bri,11] - avail[Bri,11] <= 0
 availability_constraint_for_Bri-12: s[Bri,12] - avail[Bri,12] <= 0
 availability_constraint_for_Bri-13: s[Bri,13] - avail[Bri,13] <= 0
 availability_constraint_for_Alex-0: s[Alex,0] - avail[Alex,0] <= 0
 availability_constraint_for_Alex-1: s[Alex,1] - avail[Alex,1] <= 0
 availability_constraint_for_Alex-2: s[Alex,2] - avail[Alex,2] <= 0
 availability_constraint_for_Alex-3: s[Alex,3] - avail[Alex,3] <= 0
 availability_constraint_for_Alex-4: s[Alex,4] - avail[Alex,4] <= 0
 availability_constraint_for_Alex-5: s[Alex,5] - avail[Alex,5] <= 0
 availability_constraint_for_Alex-6: s[Alex,6] - avail[Alex,6] <= 0
 availability_constraint_for_Alex-7: s[Alex,7] - avail[Alex,7] <= 0
 availability_constraint_for_Alex-8: s[Alex,8] - avail[Alex,8] <= 0
 availability_constraint_for_Alex-9: s[Alex,9] - avail[Alex,9] <= 0
 availability_constraint_for_Alex-10: s[Alex,10] - avail[Alex,10] <= 0
 availability_constraint_for_Alex-11: s[Alex,11] - avail[Alex,11] <= 0
 availability_constraint_for_Alex-12: s[Alex,12] - avail[Alex,12] <= 0
 availability_constraint_for_Alex-13: s[Alex,13] - avail[Alex,13] <= 0
 max_daily_hours: s[Tom,0] + s[Tom,1] + s[Tom,2] + s[Tom,3] + s[Tom,4]
   + s[Tom,5] + s[Tom,6] + s[Tom,7] + s[Tom,8] + s[Tom,9] + s[Tom,10]
   + s[Tom,11] + s[Tom,12] + s[Tom,13] <= 11
 max_daily_hours: s[Bri,0] + s[Bri,1] + s[Bri,2] + s[Bri,3] + s[Bri,4]
   + s[Bri,5] + s[Bri,6] + s[Bri,7] + s[Bri,8] + s[Bri,9] + s[Bri,10]
   + s[Bri,11] + s[Bri,12] + s[Bri,13] <= 11
 max_daily_hours: s[Alex,0] + s[Alex,1] + s[Alex,2] + s[Alex,3] + s[Alex,4]
   + s[Alex,5] + s[Alex,6] + s[Alex,7] + s[Alex,8] + s[Alex,9] + s[Alex,10]
   + s[Alex,11] + s[Alex,12] + s[Alex,13] <= 11
 min_workers: s[Tom,1] + s[Bri,1] + s[Alex,1] >= 1
 min_workers: s[Tom,2] + s[Bri,2] + s[Alex,2] >= 1
 min_workers: s[Tom,3] + s[Bri,3] + s[Alex,3] >= 2
 min_workers: s[Tom,4] + s[Bri,4] + s[Alex,4] >= 2
 min_workers: s[Tom,5] + s[Bri,5] + s[Alex,5] >= 2
 min_workers: s[Tom,6] + s[Bri,6] + s[Alex,6] >= 1
 min_workers: s[Tom,7] + s[Bri,7] + s[Alex,7] >= 1
 min_workers: s[Tom,8] + s[Bri,8] + s[Alex,8] >= 1
 min_workers: s[Tom,9] + s[Bri,9] + s[Alex,9] >= 2
 min_workers: s[Tom,10] + s[Bri,10] + s[Alex,10] >= 1
 min_workers: s[Tom,11] + s[Bri,11] + s[Alex,11] >= 1
 min_workers: s[Tom,12] + s[Bri,12] + s[Alex,12] >= 1
 min_workers: s[Tom,13] + s[Bri,13] + s[Alex,13] >= 1
 shift_changes[Tom,1]: s[Tom,0] - s[Tom,1] + w[Tom,1] = 0
 shift_changes[Tom,2]: s[Tom,1] - s[Tom,2] + w[Tom,2] = 0
 shift_changes[Tom,3]: s[Tom,2] - s[Tom,3] + w[Tom,3] = 0
 shift_changes[Tom,4]: s[Tom,3] - s[Tom,4] + w[Tom,4] = 0
 shift_changes[Tom,5]: s[Tom,4] - s[Tom,5] + w[Tom,5] = 0
 shift_changes[Tom,6]: s[Tom,5] - s[Tom,6] + w[Tom,6] = 0
 shift_changes[Tom,7]: s[Tom,6] - s[Tom,7] + w[Tom,7] = 0
 shift_changes[Tom,8]: s[Tom,7] - s[Tom,8] + w[Tom,8] = 0
 shift_changes[Tom,9]: s[Tom,8] - s[Tom,9] + w[Tom,9] = 0
 shift_changes[Tom,10]: s[Tom,9] - s[Tom,10] + w[Tom,10] = 0
 shift_changes[Tom,11]: s[Tom,10] - s[Tom,11] + w[Tom,11] = 0
 shift_changes[Tom,12]: s[Tom,11] - s[Tom,12] + w[Tom,12] = 0
 shift_changes[Tom,13]: s[Tom,12] - s[Tom,13] + w[Tom,13] = 0
 shift_changes[Bri,1]: s[Bri,0] - s[Bri,1] + w[Bri,1] = 0
 shift_changes[Bri,2]: s[Bri,1] - s[Bri,2] + w[Bri,2] = 0
 shift_changes[Bri,3]: s[Bri,2] - s[Bri,3] + w[Bri,3] = 0
 shift_changes[Bri,4]: s[Bri,3] - s[Bri,4] + w[Bri,4] = 0
 shift_changes[Bri,5]: s[Bri,4] - s[Bri,5] + w[Bri,5] = 0
 shift_changes[Bri,6]: s[Bri,5] - s[Bri,6] + w[Bri,6] = 0
 shift_changes[Bri,7]: s[Bri,6] - s[Bri,7] + w[Bri,7] = 0
 shift_changes[Bri,8]: s[Bri,7] - s[Bri,8] + w[Bri,8] = 0
 shift_changes[Bri,9]: s[Bri,8] - s[Bri,9] + w[Bri,9] = 0
 shift_changes[Bri,10]: s[Bri,9] - s[Bri,10] + w[Bri,10] = 0
 shift_changes[Bri,11]: s[Bri,10] - s[Bri,11] + w[Bri,11] = 0
 shift_changes[Bri,12]: s[Bri,11] - s[Bri,12] + w[Bri,12] = 0
 shift_changes[Bri,13]: s[Bri,12] - s[Bri,13] + w[Bri,13] = 0
 shift_changes[Alex,1]: s[Alex,0] - s[Alex,1] + w[Alex,1] = 0
 shift_changes[Alex,2]: s[Alex,1] - s[Alex,2] + w[Alex,2] = 0
 shift_changes[Alex,3]: s[Alex,2] - s[Alex,3] + w[Alex,3] = 0
 shift_changes[Alex,4]: s[Alex,3] - s[Alex,4] + w[Alex,4] = 0
 shift_changes[Alex,5]: s[Alex,4] - s[Alex,5] + w[Alex,5] = 0
 shift_changes[Alex,6]: s[Alex,5] - s[Alex,6] + w[Alex,6] = 0
 shift_changes[Alex,7]: s[Alex,6] - s[Alex,7] + w[Alex,7] = 0
 shift_changes[Alex,8]: s[Alex,7] - s[Alex,8] + w[Alex,8] = 0
 shift_changes[Alex,9]: s[Alex,8] - s[Alex,9] + w[Alex,9] = 0
 shift_changes[Alex,10]: s[Alex,9] - s[Alex,10] + w[Alex,10] = 0
 shift_changes[Alex,11]: s[Alex,10] - s[Alex,11] + w[Alex,11] = 0
 shift_changes[Alex,12]: s[Alex,11] - s[Alex,12] + w[Alex,12] = 0
 shift_changes[Alex,13]: s[Alex,12] - s[Alex,13] + w[Alex,13] = 0
 shift_starts_init[Tom]: - s[Tom,0] + w[Tom,0] = 0
 shift_starts_init[Bri]: - s[Bri,0] + w[Bri,0] = 0
 shift_starts_init[Alex]: - s[Alex,0] + w[Alex,0] = 0
 shift_start_max[Tom]: v[Tom,0] + v[Tom,1] + v[Tom,2] + v[Tom,3] + v[Tom,4]
   + v[Tom,5] + v[Tom,6] + v[Tom,7] + v[Tom,8] + v[Tom,9] + v[Tom,10]
   + v[Tom,11] + v[Tom,12] + v[Tom,13] <= 1
 shift_start_max[Bri]: v[Bri,0] + v[Bri,1] + v[Bri,2] + v[Bri,3] + v[Bri,4]
   + v[Bri,5] + v[Bri,6] + v[Bri,7] + v[Bri,8] + v[Bri,9] + v[Bri,10]
   + v[Bri,11] + v[Bri,12] + v[Bri,13] <= 1
 shift_start_max[Alex]: v[Alex,0] + v[Alex,1] + v[Alex,2] + v[Alex,3]
   + v[Alex,4] + v[Alex,5] + v[Alex,6] + v[Alex,7] + v[Alex,8] + v[Alex,9]
   + v[Alex,10] + v[Alex,11] + v[Alex,12] + v[Alex,13] <= 1
Bounds
 -1 <= w[Tom,0] <= 1
 -1 <= w[Tom,1] <= 1
 -1 <= w[Tom,2] <= 1
 -1 <= w[Tom,3] <= 1
 -1 <= w[Tom,4] <= 1
 -1 <= w[Tom,5] <= 1
 -1 <= w[Tom,6] <= 1
 -1 <= w[Tom,7] <= 1
 -1 <= w[Tom,8] <= 1
 -1 <= w[Tom,9] <= 1
 -1 <= w[Tom,10] <= 1
 -1 <= w[Tom,11] <= 1
 -1 <= w[Tom,12] <= 1
 -1 <= w[Tom,13] <= 1
 -1 <= w[Bri,0] <= 1
 -1 <= w[Bri,1] <= 1
 -1 <= w[Bri,2] <= 1
 -1 <= w[Bri,3] <= 1
 -1 <= w[Bri,4] <= 1
 -1 <= w[Bri,5] <= 1
 -1 <= w[Bri,6] <= 1
 -1 <= w[Bri,7] <= 1
 -1 <= w[Bri,8] <= 1
 -1 <= w[Bri,9] <= 1
 -1 <= w[Bri,10] <= 1
 -1 <= w[Bri,11] <= 1
 -1 <= w[Bri,12] <= 1
 -1 <= w[Bri,13] <= 1
 -1 <= w[Alex,0] <= 1
 -1 <= w[Alex,1] <= 1
 -1 <= w[Alex,2] <= 1
 -1 <= w[Alex,3] <= 1
 -1 <= w[Alex,4] <= 1
 -1 <= w[Alex,5] <= 1
 -1 <= w[Alex,6] <= 1
 -1 <= w[Alex,7] <= 1
 -1 <= w[Alex,8] <= 1
 -1 <= w[Alex,9] <= 1
 -1 <= w[Alex,10] <= 1
 -1 <= w[Alex,11] <= 1
 -1 <= w[Alex,12] <= 1
 -1 <= w[Alex,13] <= 1
Binaries
 s[Tom,0] s[Tom,1] s[Tom,2] s[Tom,3] s[Tom,4] s[Tom,5] s[Tom,6] s[Tom,7]
 s[Tom,8] s[Tom,9] s[Tom,10] s[Tom,11] s[Tom,12] s[Tom,13] s[Bri,0]
 s[Bri,1] s[Bri,2] s[Bri,3] s[Bri,4] s[Bri,5] s[Bri,6] s[Bri,7] s[Bri,8]
 s[Bri,9] s[Bri,10] s[Bri,11] s[Bri,12] s[Bri,13] s[Alex,0] s[Alex,1]
 s[Alex,2] s[Alex,3] s[Alex,4] s[Alex,5] s[Alex,6] s[Alex,7] s[Alex,8]
 s[Alex,9] s[Alex,10] s[Alex,11] s[Alex,12] s[Alex,13] avail[Tom,0]
 avail[Tom,1] avail[Tom,2] avail[Tom,3] avail[Tom,4] avail[Tom,5]
 avail[Tom,6] avail[Tom,7] avail[Tom,8] avail[Tom,9] avail[Tom,10]
 avail[Tom,11] avail[Tom,12] avail[Tom,13] avail[Bri,0] avail[Bri,1]
 avail[Bri,2] avail[Bri,3] avail[Bri,4] avail[Bri,5] avail[Bri,6]
 avail[Bri,7] avail[Bri,8] avail[Bri,9] avail[Bri,10] avail[Bri,11]
 avail[Bri,12] avail[Bri,13] avail[Alex,0] avail[Alex,1] avail[Alex,2]
 avail[Alex,3] avail[Alex,4] avail[Alex,5] avail[Alex,6] avail[Alex,7]
 avail[Alex,8] avail[Alex,9] avail[Alex,10] avail[Alex,11] avail[Alex,12]
 avail[Alex,13]
General Constraints
 shift_starts[Tom,1]: v[Tom,1] = MAX ( w[Tom,1] , 0 )
 shift_starts[Tom,2]: v[Tom,2] = MAX ( w[Tom,2] , 0 )
 shift_starts[Tom,3]: v[Tom,3] = MAX ( w[Tom,3] , 0 )
 shift_starts[Tom,4]: v[Tom,4] = MAX ( w[Tom,4] , 0 )
 shift_starts[Tom,5]: v[Tom,5] = MAX ( w[Tom,5] , 0 )
 shift_starts[Tom,6]: v[Tom,6] = MAX ( w[Tom,6] , 0 )
 shift_starts[Tom,7]: v[Tom,7] = MAX ( w[Tom,7] , 0 )
 shift_starts[Tom,8]: v[Tom,8] = MAX ( w[Tom,8] , 0 )
 shift_starts[Tom,9]: v[Tom,9] = MAX ( w[Tom,9] , 0 )
 shift_starts[Tom,10]: v[Tom,10] = MAX ( w[Tom,10] , 0 )
 shift_starts[Tom,11]: v[Tom,11] = MAX ( w[Tom,11] , 0 )
 shift_starts[Tom,12]: v[Tom,12] = MAX ( w[Tom,12] , 0 )
 shift_starts[Tom,13]: v[Tom,13] = MAX ( w[Tom,13] , 0 )
 shift_starts[Bri,1]: v[Bri,1] = MAX ( w[Bri,1] , 0 )
 shift_starts[Bri,2]: v[Bri,2] = MAX ( w[Bri,2] , 0 )
 shift_starts[Bri,3]: v[Bri,3] = MAX ( w[Bri,3] , 0 )
 shift_starts[Bri,4]: v[Bri,4] = MAX ( w[Bri,4] , 0 )
 shift_starts[Bri,5]: v[Bri,5] = MAX ( w[Bri,5] , 0 )
 shift_starts[Bri,6]: v[Bri,6] = MAX ( w[Bri,6] , 0 )
 shift_starts[Bri,7]: v[Bri,7] = MAX ( w[Bri,7] , 0 )
 shift_starts[Bri,8]: v[Bri,8] = MAX ( w[Bri,8] , 0 )
 shift_starts[Bri,9]: v[Bri,9] = MAX ( w[Bri,9] , 0 )
 shift_starts[Bri,10]: v[Bri,10] = MAX ( w[Bri,10] , 0 )
 shift_starts[Bri,11]: v[Bri,11] = MAX ( w[Bri,11] , 0 )
 shift_starts[Bri,12]: v[Bri,12] = MAX ( w[Bri,12] , 0 )
 shift_starts[Bri,13]: v[Bri,13] = MAX ( w[Bri,13] , 0 )
 shift_starts[Alex,1]: v[Alex,1] = MAX ( w[Alex,1] , 0 )
 shift_starts[Alex,2]: v[Alex,2] = MAX ( w[Alex,2] , 0 )
 shift_starts[Alex,3]: v[Alex,3] = MAX ( w[Alex,3] , 0 )
 shift_starts[Alex,4]: v[Alex,4] = MAX ( w[Alex,4] , 0 )
 shift_starts[Alex,5]: v[Alex,5] = MAX ( w[Alex,5] , 0 )
 shift_starts[Alex,6]: v[Alex,6] = MAX ( w[Alex,6] , 0 )
 shift_starts[Alex,7]: v[Alex,7] = MAX ( w[Alex,7] , 0 )
 shift_starts[Alex,8]: v[Alex,8] = MAX ( w[Alex,8] , 0 )
 shift_starts[Alex,9]: v[Alex,9] = MAX ( w[Alex,9] , 0 )
 shift_starts[Alex,10]: v[Alex,10] = MAX ( w[Alex,10] , 0 )
 shift_starts[Alex,11]: v[Alex,11] = MAX ( w[Alex,11] , 0 )
 shift_starts[Alex,12]: v[Alex,12] = MAX ( w[Alex,12] , 0 )
 shift_starts[Alex,13]: v[Alex,13] = MAX ( w[Alex,13] , 0 )
End
