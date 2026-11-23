import json
from pathlib import Path
from .memory import load_memory,fetch_relevant_records , update_memory
from .checks import perform_checks
from .confidence import assign_confidence_value

class Reasoning:
    def __init__ ( self, fixed_attributes = [ 'color' , 'size','brand' , 'material',
                                              'use_case','target_user' , 'others']) :
        self.fixed_attributes = fixed_attributes 

    def add_safe_preferences( self , input_schema ,user_id ) :
        memory_data = load_memory(user_id)
        relevant_records = fetch_relevant_records( input_schema , memory_data )
        assessed_records = perform_checks( relevant_records, input_schema , self.fixed_attributes )
        confidence_assigned = assign_confidence_value ( assessed_records,self.fixed_attributes )
        assessed_records = [
                                record
                                for category_records in confidence_assigned
                                for record in category_records
        ]
        update_memory ( input_schema, memory_data)
        return assessed_records