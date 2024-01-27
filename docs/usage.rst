*****
Usage
*****

To use Apitit in a project::

   from apitit import Apitit
   from pprint import pprint

   card_number = 123456
   password = "super secret password"
   
   apt = Apitit("Paderborn", card_number, password)
   trans_pos = apt.get_transaction_positions()

   pprint(trans_pos)
