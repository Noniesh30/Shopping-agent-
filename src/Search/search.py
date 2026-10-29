
from src.Search.product_search import search_products
import json
import pandas as pd

class Searching:
    def __init__(self,products,categories):
        print("Getting all the Data")
        self.products, self.categories = products,categories
        self.nodes_explored = 0
        self.backtracks = 0
        self.top_k_solutions=10

    def get_domains(self, requirements):
        domains = {}
        total_possible_combinations=1
        for item in requirements["items"]:
            item_name = item["name"]
            category_ids = item["category_id"]

            if not isinstance(category_ids, list):
                category_ids = [category_ids]

            products = self.products
            domain = products[
                products["asin"].notna()&
                products["title"].notna()&
                products["category_id"].isin(category_ids) &
                products["price_inr"].notna() &
                products["stars"].notna() &
                products["reviews"].notna()&
                products["imgUrl"].notna()
            ]


            if item.get("budget") is not None:
                domain = domain[domain["price_inr"] <= item["budget"]]

            if item.get("min_rating") is not None:
                domain = domain[
                    domain["stars"] >= item["min_rating"]
                ]

            if item.get("min_reviews") is not None:
                domain = domain[
                    domain["reviews"] >= item["min_reviews"]
                ]

            #Searching According to the Name 
            # if item.get("keywords") is not None:
            #     for keyword in item["keywords"]:
            #         domain = domain[domain["title"].astype(str).str.contains(keyword, case=False, na=False)] 

            # if item.get("preferences") is not None:
            #     for preference in item["preferences"]:
            #         domain = domain[domain["title"].astype(str).str.contains(preference, case=False, na=False)]

            domain = search_products(domain, item)
            domains[item_name] = domain 
            total_possible_combinations*=len(domain)
            print(item_name, "domain size:", len(domain))

        return domains,total_possible_combinations

    def is_consistent(self, assignment, new_product, item, requirements):
        for product in assignment.values():
            if product["asin"] == new_product["asin"]:
                return False

        if item.get("budget") is not None:
            if new_product["price_inr"] > item["budget"]:
                return False

        if item.get("min_rating") is not None:
            if new_product["stars"] < item["min_rating"]:
                return False

        if item.get("min_reviews") is not None:
            if new_product["reviews"] < item["min_reviews"]:
                return False

        total_cost = new_product["price_inr"]
        for product in assignment.values():
            total_cost += product["price_inr"]

        if requirements.get("budget") is not None:
            if total_cost > requirements["budget"]:
                return False

        return True

   
    def backtracking_search(
        self, variables, domains, assignment, requirements, items,
        solutions, max_solutions
    ):
        if len(solutions) >= max_solutions:
            return

        if len(assignment) == len(variables):
            solutions.append(assignment.copy())
            return

        variable = variables[len(assignment)]
        item = items[variable]

        for index in domains[variable].index:
            if len(solutions) >= max_solutions:
                return

            self.nodes_explored += 1
            product = self.products.loc[index]

            if self.is_consistent(
                assignment, product, item, requirements
            ):
                assignment[variable] = product

                self.backtracking_search(
                    variables, domains, assignment, requirements, items,
                    solutions, max_solutions
                )

                del assignment[variable]

    def json_compatiable(self,solutions):

        results=[]
        for solution in solutions:
            result = {
                category: series.to_dict()
                for category, series in solution.items()
            }
            results.append(result)
            
        return results

    def finding_products(self, requirements):
        print(requirements)

        variables = [item["name"] for item in requirements["items"]]
        items = {item["name"]: item for item in requirements["items"]}

        self.nodes_explored = 0
        self.backtracks = 0

        domains,total_possible_combinations = self.get_domains(requirements)
        print("Total Possible Combiantions:",total_possible_combinations)

        #Top solutions 
        # self.top_k_solutions=10

        # Fail early if any item has an empty domain
        if any(domains[v].empty for v in variables):
            print("NO FEASIBLE SOLUTION: One or more domains are empty.")
            return None

        solutions = []

        self.backtracking_search(
            variables, domains, {}, requirements, items,
            solutions, max_solutions=self.top_k_solutions
        )

        if not solutions:
            print("NO FEASIBLE SOLUTION FOUND")
        else:
            for i, solution in enumerate(solutions, 1):
                print(f"\nSolution {i}")

                total_cost = 0

                for variable, product in solution.items():
                    print("Item:", variable)
                    print("Product:", product["title"])
                    print("Price:", product["price_inr"])
                    print("Category:", product["category_id"])
                    total_cost += product["price_inr"]

                print("------------------------")
                print("Total cost:", total_cost)


        print("Budget:", requirements.get("budget"))
        print("Nodes explored:", self.nodes_explored)
        print("Backtracks:", self.backtracks)

        return self.json_compatiable(solutions)
