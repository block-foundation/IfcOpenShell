# IfcTester - IDS based model auditing
# Copyright (C) 2021 Artur Tomczak <artomczak@gmail.com>, Thomas Krijnen <mail@thomaskrijnen.com>, Dion Moult <dion@thinkmoult.com>
#
# This file is part of IfcTester.
#
# IfcTester is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IfcTester is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with IfcTester.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import math
import logging
import datetime
import ifcopenshell
import ifcopenshell.util.element

cwd = os.path.dirname(os.path.realpath(__file__))


class Reporter:
    def __init__(self, ids):
        self.ids = ids

    def report(self, ids):
        pass

    def to_string(self):
        return ""

    def write(self, filepath):
        pass


class Console(Reporter):
    def __init__(self, ids, use_colour=True):
        super().__init__(ids)
        self.use_colour = use_colour
        self.colours = {
            "red": "\033[1;31m",
            "blue": "\033[1;34m",
            "cyan": "\033[1;36m",
            "green": "\033[0;32m",
            "yellow": "\033[0;33m",
            "purple": "\033[0;95m",
            "grey": "\033[0;90m",
            "reset": "\033[0;0m",
            "bold": "\033[;1m",
            "reverse": "\033[;7m",
        }

    def report(self):
        self.set_style("bold", "blue")
        self.print(self.ids.info.get("title", "Untitled IDS"))
        for specification in self.ids.specifications:
            self.report_specification(specification)
        self.set_style("reset")

    def report_specification(self, specification):
        if specification.status is True:
            self.set_style("bold", "green")
            self.print("[PASS] ", end="")
        elif specification.status is False:
            self.set_style("bold", "red")
            self.print("[FAIL] ", end="")
        elif specification.status is None:
            self.set_style("bold", "yellow")
            self.print("[UNTESTED] ", end="")

        self.set_style("bold")
        total = len(specification.applicable_entities)
        total_successes = total - len(specification.failed_entities)
        self.print(f"({total_successes}/{total}) ", end="")

        if specification.minOccurs != 0:
            self.print(f"*", end="")

        self.print(specification.name)

        self.set_style("cyan")
        self.print(" " * 4 + "Applies to:")
        self.set_style("reset")

        for applicability in specification.applicability:
            self.print(" " * 8 + applicability.to_string("applicability"))

        if not total and specification.status is False:
            return

        self.set_style("cyan")
        self.print(" " * 4 + "Requirements:")
        self.set_style("reset")

        for requirement in specification.requirements:
            self.set_style("reset")
            self.set_style("red") if requirement.failed_entities else self.set_style("green")
            self.print(" " * 8 + requirement.to_string("requirement"))
            self.set_style("reset")
            for i, element in enumerate(requirement.failed_entities[0:10]):
                self.print(" " * 12, end="")
                self.report_reason(requirement.failed_reasons[i], element)
            if len(requirement.failed_entities) > 10:
                self.print(" " * 12 + f"... {len(requirement.failed_entities)} in total ...")
        self.set_style("reset")

    def report_reason(self, reason, element):
        is_bold = False
        for substring in reason.split('"'):
            if is_bold:
                self.set_style("purple")
            else:
                self.set_style("reset")
            self.print(substring, end="")
            is_bold = not is_bold
        self.set_style("grey")
        self.print(" - " + str(element))
        self.set_style("reset")

    def set_style(self, *colours):
        if self.use_colour:
            sys.stdout.write("".join([self.colours[c] for c in colours]))

    def print(self, txt, end=None):
        if end is not None:
            print(txt, end=end)
        else:
            print(txt)


class Txt(Console):
    def __init__(self, ids):
        super().__init__(ids, use_colour=False)
        self.text = ""

    def print(self, txt, end=None):
        self.text += txt + "\n" if end is None else txt

    def to_string(self):
        print(self.text)

    def to_file(self, filepath):
        with open(filepath, "w") as outfile:
            return outfile.write(self.text)


class Json(Reporter):
    def __init__(self, ids):
        super().__init__(ids)
        self.results = {}

    def report(self):
        self.results["title"] = self.ids.info.get("title", "Untitled IDS")
        self.results["specifications"] = []
        for specification in self.ids.specifications:
            self.results["specifications"].append(self.report_specification(specification))
        return self.results

    def report_specification(self, specification):
        applicability = [a.to_string("applicability") for a in specification.applicability]
        requirements = []
        for requirement in specification.requirements:
            requirements.append(
                {
                    "description": requirement.to_string("requirement"),
                    "status": requirement.status,
                    "failed_entities": self.report_failed_entities(requirement),
                }
            )
        total = len(specification.applicable_entities)
        total_successes = total - len(specification.failed_entities)
        percentage = math.floor((total_successes / total) * 100) if total else "N/A"
        return {
            "name": specification.name,
            "status": specification.status,
            "total_successes": total_successes,
            "total": total,
            "percentage": percentage,
            "required": specification.minOccurs != 0,
            "applicability": applicability,
            "requirements": requirements,
        }

    def report_failed_entities(self, requirement):
        return [
            {
                "reason": requirement.failed_reasons[i],
                "element": str(e),
                "class": e.is_a(),
                "predefined_type": ifcopenshell.util.element.get_predefined_type(e),
                "name": getattr(e, "Name", None),
                "description": getattr(e, "Description", None),
                "id": e.id(),
                "global_id": getattr(e, "GlobalId", None),
                "tag": getattr(e, "Tag", None),
            }
            for i, e in enumerate(requirement.failed_entities)
        ]

    def to_string(self):
        import json

        return json.dumps(self.results)

    def to_file(self, filepath):
        import json

        with open(filepath, "w") as outfile:
            return json.dump(self.results, outfile)


class Html(Json):
    def __init__(self, ids):
        super().__init__(ids)
        self.results = {}

    def report(self):
        self.results["title"] = self.ids.info.get("title", "Untitled IDS")
        self.results["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.results["specifications"] = []
        for specification in self.ids.specifications:
            self.results["specifications"].append(self.report_specification(specification))
        return self.results

    def to_string(self):
        import pystache

        with open(os.path.join(cwd, "templates", "report.html"), "r") as file:
            return pystache.render(file.read(), self.results)

    def to_file(self, filepath):
        import pystache

        with open(os.path.join(cwd, "templates", "report.html"), "r") as file:
            with open(filepath, "w") as outfile:
                return outfile.write(pystache.render(file.read(), self.results))


class Ods(Json):
    def __init__(self, ids):
        super().__init__(ids)
        self.colours = {
            "h": "cccccc",  # Header
            "p": "97cc64",  # Pass
            "f": "fb5a3e",  # Fail
            "t": "ffffff",  # Regular text
        }
        self.results = {}

    def to_file(self, filepath):
        from odf.opendocument import OpenDocumentSpreadsheet
        from odf.style import Style, TableCellProperties
        from odf.table import Table, TableRow, TableCell
        from odf.text import P

        self.doc = OpenDocumentSpreadsheet()

        self.cell_formats = {}
        for key, value in self.colours.items():
            style = Style(name=key, family="table-cell")
            style.addElement(TableCellProperties(backgroundcolor="#" + value))
            self.doc.automaticstyles.addElement(style)
            self.cell_formats[key] = style

        table = Table(name=self.results["title"])
        tr = TableRow()
        for header in ["Specification", "Status", "Total Compliant", "Total Applicable", "Percentage Compliant"]:
            tc = TableCell(valuetype="string", stylename="h")
            tc.addElement(P(text=header))
            tr.addElement(tc)
        table.addElement(tr)

        rows = []
        for specification in self.results["specifications"]:
            rows.append(
                [
                    specification["name"],
                    "Pass" if specification["status"] else "Fail",
                    str(specification["total_successes"]),
                    str(specification["total"]),
                    str(specification["percentage"]),
                ]
            )

        for row in rows:
            tr = TableRow()
            c = 0
            stylename = "p" if row[1] == "Pass" else "f"
            for col in row:
                tc = TableCell(valuetype="string", stylename=stylename)
                if col is None:
                    col = "NULL"
                tc.addElement(P(text=col))
                tr.addElement(tc)
                c += 1
            table.addElement(tr)
        self.doc.spreadsheet.addElement(table)

        for specification in self.results["specifications"]:
            if specification["status"]:
                continue
            table = Table(name=specification["name"])
            tr = TableRow()
            for header in ["Requirement", "Problem", "Element"]:
                tc = TableCell(valuetype="string", stylename="h")
                tc.addElement(P(text=header))
                tr.addElement(tc)
            table.addElement(tr)
            for requirement in specification["requirements"]:
                if requirement["status"]:
                    continue
                for failure in requirement["failed_entities"]:
                    row = [
                        requirement["description"],
                        failure.get("reason", "No reason provided"),
                        str(failure.get("element", "No element found")),
                    ]
                    tr = TableRow()
                    c = 0
                    for col in row:
                        tc = TableCell(valuetype="string", stylename="t")
                        if col is None:
                            col = "NULL"
                        tc.addElement(P(text=col))
                        tr.addElement(tc)
                        c += 1
                    table.addElement(tr)
            self.doc.spreadsheet.addElement(table)

        self.doc.save(filepath, True)


class Bcf(Json):
    def report_failed_entities(self, requirement):
        return [
            {"reason": requirement.failed_reasons[i], "element": e} for i, e in enumerate(requirement.failed_entities)
        ]

    def to_file(self, filepath):
        from bcf.v2.bcfxml import BcfXml

        bcfxml = BcfXml.create_new(self.results["title"])
        for specification in self.results["specifications"]:
            if specification["status"]:
                continue
            for requirement in specification["requirements"]:
                if requirement["status"]:
                    continue
                for failure in requirement["failed_entities"]:
                    element = failure["element"]
                    title = f"ID:[{element.id()}]/GUID:[{element.GlobalId}]/{element.is_a()}/"
                    title += getattr(element, "Name", None) or "Unnamed"
                    title += " - " + failure.get("reason", "No reason")
                    description = f'{specification["name"]} - {requirement["description"]}'
                    topic = bcfxml.add_topic(title, description, "IfcTester")
                    if element.is_a("IfcElement"):
                        topic.add_viewpoint(element)
        bcfxml.save_project(filepath)
